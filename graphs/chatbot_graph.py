import asyncio
import logging
from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from config.prompts import (ADMIN_APPROVAL_CONFIRMATION_PROMPT,
                            ADMIN_REJECTION_MESSAGE_PROMPT,
                            ADMIN_REVIEW_PROMPT, ASK_CAR_PLATE_MESSAGE,
                            ASK_DATES_MESSAGE, ASK_NAME_MESSAGE,
                            ASK_SURNAME_MESSAGE, CONFIRM_DATA_PROMPT,
                            INVALID_INPUT_MESSAGE,
                            PENDING_APPROVAL_USER_MESSAGE)
from core.data_extractor import get_data_extractor
from core.rag import get_rag_system
from graphs.state import (ChatbotState, ReservationData, ReservationStatus,
                          create_initial_state)
from guardrails.pii_protection import get_guardrails_manager
from mcp_client.client import get_mcp_client

logger = logging.getLogger(__name__)


class ParkingChatbot:
    """Main chatbot with LangGraph state machine"""

    MAX_RETRIES = 3  # Maximum retries for each field

    def __init__(self):
        logger.info("Initializing Parking Chatbot...")
        self.rag_system = get_rag_system()
        self.guardrails = get_guardrails_manager()
        self.data_extractor = get_data_extractor()
        self.graph = self._build_graph()         
        logger.info("Parking Chatbot initialized")
    
    def _build_graph(self) -> StateGraph:        
        workflow = StateGraph(ChatbotState)

        # Add nodes
        workflow.add_node("check_guardrails", self._check_guardrails)
        workflow.add_node("check_reservation_status", self._check_reservation_status)
        workflow.add_node("check_reservation_intent", self._check_reservation_intent)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("handle_unsafe_input", self._handle_unsafe_input)

        # Reservation collection nodes
        workflow.add_node("start_reservation", self._start_reservation)
        workflow.add_node("collect_name", self._collect_name)
        workflow.add_node("collect_surname", self._collect_surname)
        workflow.add_node("collect_car_plate", self._collect_car_plate)
        workflow.add_node("collect_dates", self._collect_dates)
        workflow.add_node("confirm_reservation", self._confirm_reservation)
        workflow.add_node("finalize_reservation", self._finalize_reservation)

        # Admin Agent nodes
        workflow.add_node("format_for_admin", self._format_for_admin)
        workflow.add_node("wait_for_admin_decision", self._wait_for_admin_decision)
        workflow.add_node("process_admin_approval", self._process_admin_approval)
        workflow.add_node("process_admin_rejection", self._process_admin_rejection)
        workflow.add_node("persist_to_mcp", self._persist_to_mcp_node)
        workflow.add_node("notify_user_final", self._notify_user_final)

        # Add edges
        workflow.add_edge(START, "check_guardrails")

        workflow.add_conditional_edges(
            "check_guardrails",
            self._route_after_guardrails,
            {
                "safe": "check_reservation_status",
                "unsafe": "handle_unsafe_input"
            }
        )

        workflow.add_conditional_edges(
            "check_reservation_status",
            self._route_after_status_check,
            {
                "status_query": END,
                "continue": "check_reservation_intent"
            }
        )

        workflow.add_conditional_edges(
            "check_reservation_intent",
            self._route_after_intent_check,
            {
                "new_reservation": "start_reservation",
                "continue_reservation": "collect_name",
                "normal_query": "retrieve_context"
            }
        )

        workflow.add_edge("retrieve_context", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_unsafe_input", END)

        # Reservation flow edges
        workflow.add_edge("start_reservation", END)

        workflow.add_conditional_edges(
            "collect_name",
            self._route_after_name,
            {
                "next_field": "collect_surname",
                "asked_question": END,
                "retry": "collect_name",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "collect_surname",
            self._route_after_surname,
            {
                "next_field": "collect_car_plate",
                "asked_question": END,
                "retry": "collect_surname",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "collect_car_plate",
            self._route_after_car_plate,
            {
                "next_field": "collect_dates",
                "asked_question": END,
                "retry": "collect_car_plate",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "collect_dates",
            self._route_after_dates,
            {
                "next_field": "confirm_reservation",
                "asked_question": END,
                "retry": "collect_dates",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "confirm_reservation",
            self._route_after_confirmation,
            {
                "confirmed": "finalize_reservation",
                "rejected": "collect_name",
                "fail": END
            }
        )

        workflow.add_edge("finalize_reservation", "format_for_admin")
        workflow.add_edge("format_for_admin", "wait_for_admin_decision")

        # Conditional routing after admin decision
        workflow.add_conditional_edges(
            "wait_for_admin_decision",
            self._route_after_admin_decision,
            {
                "approved": "process_admin_approval",
                "rejected": "process_admin_rejection",
                "waiting": "wait_for_admin_decision"
            }
        )

        # Admin approval path - goes through MCP
        workflow.add_edge("process_admin_approval", "persist_to_mcp")
        workflow.add_edge("persist_to_mcp", "notify_user_final")

        # Admin rejection path - skips MCP, goes directly to notification
        workflow.add_edge("process_admin_rejection", "notify_user_final")

        # Final notification ends the graph
        workflow.add_edge("notify_user_final", END)

        memory = MemorySaver()
        # Add interrupt_before for human-in-the-loop admin approval
        return workflow.compile(
            checkpointer=memory,
            interrupt_before=["wait_for_admin_decision"]  # Graph pauses here for admin
        )
    
    def _check_guardrails(self, state: ChatbotState) -> ChatbotState:
        logger.info("Checking guardrails...")

        if "user_input" not in state or not state.get("user_input"):
            if state.get("waiting_for_admin") or state.get("admin_decision"):
                logger.info("Skipping guardrails check (admin workflow resume)")
                state["input_safe"] = True
                return state
            logger.warning("No user_input in state and not admin workflow")
            state["input_safe"] = False
            return state

        user_input = state["user_input"]
        report = self.guardrails.check_input(user_input)
        state["input_safe"] = not report["should_block"]
        state["guardrails_report"] = report
        if not state["input_safe"]:
            logger.warning(f"Unsafe input detected: {report}")
        return state

    def _route_after_guardrails(
        self,
        state: ChatbotState
    ) -> Literal["safe", "unsafe"]:
        return "safe" if state["input_safe"] else "unsafe"

    async def _check_reservation_status(self, state: ChatbotState) -> ChatbotState:
        """Check if user is asking about reservation status and fetch latest status"""
        logger.info("Checking if user is asking about reservation status...")

        if state.get("admin_decision") or state.get("waiting_for_admin"):
            logger.info("Skipping status check (admin workflow)")
            return state

        user_input = state.get("user_input", "").lower()

        status_keywords = [
            "status", "approved", "rejected", "pending", 
            "decision", "reviewed", "confirmation",
            "what happened", "is it approved", "did admin",
            "my reservation", "my booking"
        ]

        is_status_query = any(keyword in user_input for keyword in status_keywords)

        if is_status_query and state.get("reservation_id"):
            logger.info(f"User is asking about status, checking reservation {state['reservation_id']}")

            try:
                from api.reservation_manager import get_reservation_manager

                reservation_manager = get_reservation_manager()
                reservation_id = state["reservation_id"]

                reservation = await reservation_manager.get_reservation(reservation_id)

                if reservation:
                    logger.info(f"Found reservation {reservation_id} with status: {reservation.status}")

                    if reservation.status.value == "approved":
                        state["reservation_status"] = ReservationStatus.APPROVED
                        message = f"Great news! Your reservation has been APPROVED!\n\n" \
                                f"Reservation ID: {reservation.reservation_id}\n" \
                                f"Name: {reservation.name} {reservation.surname}\n" \
                                f"Car: {reservation.car_plate}\n" \
                                f"Period: {reservation.start_time} to {reservation.end_time}\n"

                        if reservation.admin_comment:
                            message += f"\nAdmin comment: {reservation.admin_comment}\n"

                        message += "\nYou can proceed to the parking location during your reserved period."

                    elif reservation.status.value == "rejected":
                        state["reservation_status"] = ReservationStatus.REJECTED
                        message = f"Unfortunately, your reservation has been REJECTED.\n\n" \
                                f"Reservation ID: {reservation.reservation_id}\n"

                        if reservation.admin_comment:
                            message += f"\nReason: {reservation.admin_comment}\n"

                        message += "\nYou can make a new reservation if you'd like to try different dates."

                    elif reservation.status.value == "pending_approval":
                        state["reservation_status"] = ReservationStatus.PENDING_APPROVAL
                        message = f"Your reservation is still PENDING approval.\n\n" \
                                f"Reservation ID: {reservation.reservation_id}\n" \
                                f"Name: {reservation.name} {reservation.surname}\n" \
                                f"Car: {reservation.car_plate}\n" \
                                f"Period: {reservation.start_time} to {reservation.end_time}\n\n" \
                                f"An administrator will review your request shortly.\n" \
                                f"You will be notified once a decision is made."

                    elif reservation.status.value == "expired":
                        state["reservation_status"] = ReservationStatus.CANCELLED
                        message = f"Your reservation request has EXPIRED.\n\n" \
                                f"Reservation ID: {reservation.reservation_id}\n\n" \
                                f"Please submit a new reservation request if you still need parking."
                    else:
                        message = f"Your reservation status: {reservation.status.value}"

                    state["response"] = message
                    state["is_status_query"] = True
                    state["messages"] = state.get("messages", []) + [
                        HumanMessage(content=state["user_input"]),
                        AIMessage(content=message)
                    ]

                    logger.info(f"Status query answered with latest status: {reservation.status.value}")
                else:
                    logger.warning(f"Reservation {reservation_id} not found")
                    state["is_status_query"] = False

            except Exception as e:
                logger.error(f"Error checking reservation status: {e}", exc_info=True)
                state["is_status_query"] = False
        else:
            state["is_status_query"] = False

        return state

    def _route_after_status_check(
        self,
        state: ChatbotState
    ) -> Literal["status_query", "continue"]:
        """Route based on whether this was a status query"""
        if state.get("is_status_query"):
            logger.info("Status query answered, ending conversation")
            return "status_query"
        return "continue"
    
    def _check_reservation_intent(self, state: ChatbotState) -> ChatbotState:
        """Check if user wants to make a reservation or continue existing one"""
        logger.info("Checking reservation intent...")

        if state.get("admin_decision") or state.get("waiting_for_admin"):
            logger.info("Skipping reservation intent check (admin workflow)")
            return state

        current_status = state["reservation_status"]
        logger.info(f"Current reservation status: {current_status}")

        # If already in reservation process, continue
        if state["reservation_status"] != ReservationStatus.NOT_STARTED:
            logger.info(f"Continuing reservation process: {state['reservation_status']}")
            return state

        # Check if user wants to start new reservation
        logger.info(f"Checking reservation intent: {state['user_input']}")
        wants_reservation = self.data_extractor.check_reservation_intent(state["user_input"])
        state["wants_reservation"] = wants_reservation
        logger.info(f"Reservation intent: {wants_reservation}")

        if wants_reservation:
            logger.info("User wants to make a reservation")
            state["reservation_status"] = ReservationStatus.STARTED

        return state

    def _route_after_intent_check(
        self,
        state: ChatbotState
    ) -> Literal["new_reservation", "continue_reservation", "normal_query"]:
        """Route based on reservation intent"""

        if state.get("admin_decision") or state.get("waiting_for_admin"):
            logger.info("Admin workflow detected in routing - this shouldn't happen")
            return "normal_query"

        # If already collecting name (status set by start_reservation)
        if state["reservation_status"] == ReservationStatus.COLLECTING_NAME:
            return "continue_reservation"

        # If collecting other fields
        if state["reservation_status"] in [
            ReservationStatus.COLLECTING_SURNAME,
            ReservationStatus.COLLECTING_CAR_PLATE,
            ReservationStatus.COLLECTING_DATES,
            ReservationStatus.CONFIRMING
        ]:
            return "continue_reservation"

        # If just starting reservation
        if state["wants_reservation"] or state["reservation_status"] == ReservationStatus.STARTED:
            return "new_reservation"

        # Normal information query
        return "normal_query"

    def _retrieve_context(self, state: ChatbotState) -> ChatbotState:
        logger.info("Retrieving context...")

        if state.get("admin_decision") or state.get("waiting_for_admin"):
            logger.info("Skipping context retrieval (admin workflow)")
            state["retrieved_context"] = ""
            return state

        user_input = state["user_input"]
        logger.info(f"Retrieving context for: {user_input}")
        docs = self.rag_system.retrieve_context(user_input)        
        filtered_docs = self.guardrails.filter_context(docs)        
        context = "\n\n".join([doc.page_content for doc in filtered_docs])
        state["retrieved_context"] = context
        logger.info(f"Retrieved {len(filtered_docs)} documents")
        return state
    
    def _generate_response(self, state: ChatbotState) -> ChatbotState:
        logger.info("Generating response...")

        if state.get("admin_decision") or state.get("waiting_for_admin"):
            logger.info("Skipping response generation (admin workflow)")
            return state

        user_input = state["user_input"]
        logger.info(f"Generating answer for: {user_input}")
        context = state["retrieved_context"] or ""
        chat_history = state.get("messages", [])
        response = self.rag_system.generate_answer(
            question=user_input,
            chat_history=chat_history
        )        
        safe_response = self.guardrails.get_safe_response(response)        
        state["response"] = safe_response
        state["messages"] = chat_history + [
            HumanMessage(content=user_input),
            AIMessage(content=safe_response)
        ]
        logger.info("Answer generated")
        logger.info("Response generated")
        return state
    
    def _handle_unsafe_input(self, state: ChatbotState) -> ChatbotState:
        logger.warning("Handling unsafe input...")
        report = state.get("guardrails_report", {})
        if report.get("pii_detected"):
            message = (
                "I noticed you may have shared sensitive personal information. "
                "For your security, please avoid sharing details like email addresses, "
                "phone numbers, or credit card information in our chat. "
                "If you need to provide such information for your reservation, "
                "our team will contact you securely after confirmation."
            )
        else:
            message = (
                "I'm sorry, but I cannot process that request. "
                "Please rephrase your question or ask about our parking services."
            )
        
        state["response"] = message
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=state["user_input"]),
            AIMessage(content=message)
        ]
        
        return state

    def _start_reservation(self, state: ChatbotState) -> ChatbotState:
        logger.info("Starting reservation process...")
        state["reservation_status"] = ReservationStatus.COLLECTING_NAME
        state["retry_count"] = 0
        state["response"] = ASK_NAME_MESSAGE
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=state["user_input"]),
            AIMessage(content=ASK_NAME_MESSAGE)
        ]
        logger.info("Reservation process started - waiting for user's name")
        return state

    def _collect_name(self, state: ChatbotState) -> ChatbotState:
        logger.info("Collecting name...")

        # If name is already collected, skip extraction
        if state["reservation_data"].name:
            logger.info(f"Name already collected: {state['reservation_data'].name}")
            return state

        # Try to extract name from user input
        name = self.data_extractor.extract_name(state["user_input"])

        if name:
            state["reservation_data"].name = name
            logger.info(f"Name collected: {name}")
            state["retry_count"] = 0
            return state
        else:
            # Failed to extract name
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.warning(f"Failed to extract name. Retry count: {state['retry_count']}")

            if state["retry_count"] >= self.MAX_RETRIES:
                state["response"] = \
                f"I'm having trouble understanding. "
                f"Let's start over or try a different question."
                state["reservation_status"] = ReservationStatus.CANCELLED
            else:
                state["response"] = INVALID_INPUT_MESSAGE.format(
                    context="Please provide your first name (e.g., 'John' or 'My name is Sarah')."
                )

            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]

            return state

    def _route_after_name(
        self,
        state: ChatbotState
    ) -> Literal["next_field", "asked_question", "retry", "fail"]:
        """Route after name collection"""
        if state["reservation_status"] == ReservationStatus.CANCELLED:
            return "fail"

        # Data collected → move to next field
        if state["reservation_data"].name:
            return "next_field"

        # Just asked question (no data, retry_count=0) → end invoke
        if state.get("retry_count", 0) == 0 and not state["reservation_data"].name:
            logger.info("Just asked for name, ending invoke to wait for response")
            return "asked_question"

        return "retry"

    def _collect_surname(self, state: ChatbotState) -> ChatbotState:
        """Collect user's surname"""
        logger.info("Collecting surname...")

        # First time asking - transition from COLLECTING_NAME to COLLECTING_SURNAME
        if not state["reservation_data"].surname \
            and state["reservation_status"] == ReservationStatus.COLLECTING_NAME:
            state["reservation_status"] = ReservationStatus.COLLECTING_SURNAME
            state["retry_count"] = 0
            message = ASK_SURNAME_MESSAGE.format(name=state["reservation_data"].name)
            state["response"] = message
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=message)
            ]
            logger.info(f"Asked for surname, will wait for user response")
            return state

        # If surname already collected, skip
        if state["reservation_data"].surname:
            logger.info(f"Surname already collected: {state['reservation_data'].surname}")
            return state

        # Try to extract surname
        logger.info(f"Extracting surname from: {state['user_input']}")
        surname = self.data_extractor.extract_surname(state["user_input"])

        if surname:
            state["reservation_data"].surname = surname
            logger.info(f"Surname collected: {surname}")
            state["retry_count"] = 0
            return state
        else:
            logger.info("Surname not found")
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.warning(f"Failed to extract surname. Retry count: {state['retry_count']}")

            if state["retry_count"] >= self.MAX_RETRIES:
                state["response"] = \
                f"I'm having trouble understanding. "
                f"Let's start over or try a different question."
                state["reservation_status"] = ReservationStatus.CANCELLED
            else:
                state["response"] = INVALID_INPUT_MESSAGE.format(
                    context="Please provide your last name (e.g., 'Smith' or 'My surname is Johnson')."
                )

            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]

            return state

    def _route_after_surname(
        self,
        state: ChatbotState
    ) -> Literal["next_field", "asked_question", "retry", "fail"]:
        """Route after surname collection"""
        if state["reservation_status"] == ReservationStatus.CANCELLED:
            return "fail"

        # If data collected, move to next field
        if state["reservation_data"].surname:
            return "next_field"

        # If we just asked the question (retry_count is 0 and no surname yet), 
        # treat as asked_question to end this invoke and wait for user response
        if state.get("retry_count", 0) == 0 and not state["reservation_data"].surname:
            logger.info("Just asked for surname, ending invoke to wait for response")
            return "asked_question"

        return "retry"

    def _collect_car_plate(self, state: ChatbotState) -> ChatbotState:
        """Collect car plate number"""
        logger.info("Collecting car plate...")

        # First time asking
        if not state["reservation_data"].car_plate \
            and state["reservation_status"] == ReservationStatus.COLLECTING_SURNAME:
            state["reservation_status"] = ReservationStatus.COLLECTING_CAR_PLATE
            state["retry_count"] = 0
            message = ASK_CAR_PLATE_MESSAGE.format(
                name=state["reservation_data"].name,
                surname=state["reservation_data"].surname
            )
            state["response"] = message
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=message)
            ]
            return state

        # If car plate already collected, skip
        if state["reservation_data"].car_plate:
            logger.info(f"Car plate already collected: {state['reservation_data'].car_plate}")
            return state

        # Try to extract car plate
        car_plate = self.data_extractor.extract_car_plate(state["user_input"])

        if car_plate:
            state["reservation_data"].car_plate = car_plate
            logger.info(f"Car plate collected: {car_plate}")
            state["retry_count"] = 0
            return state
        else:
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.warning(f"Failed to extract car plate. Retry count: {state['retry_count']}")

            if state["retry_count"] >= self.MAX_RETRIES:
                state["response"] = \
                    f"I'm having trouble understanding. "
                f"Let's start over or try a different question."
                state["reservation_status"] = ReservationStatus.CANCELLED
            else:
                state["response"] = INVALID_INPUT_MESSAGE.format(
                    context= \
                    f"Please provide your car license plate number "
                    f"(e.g., 'ABC123' or 'My plate is XY-456-ZZ')."
                )

            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]

            return state

    def _route_after_car_plate(
        self,
        state: ChatbotState
    ) -> Literal["next_field", "asked_question", "retry", "fail"]:
        """Route after car plate collection"""
        if state["reservation_status"] == ReservationStatus.CANCELLED:
            return "fail"

        # Data collected → move to next field
        if state["reservation_data"].car_plate:
            return "next_field"

        # If we just asked the question (retry_count is 0 and no car_plate yet)
        if state.get("retry_count", 0) == 0 and not state["reservation_data"].car_plate:
            logger.info("Just asked for car plate, ending invoke to wait for response")
            return "asked_question"

        return "retry"

    def _collect_dates(self, state: ChatbotState) -> ChatbotState:
        """Collect reservation dates"""
        logger.info("Collecting dates...")

        # First time asking
        if not state["reservation_data"].start_time and state["reservation_status"] == ReservationStatus.COLLECTING_CAR_PLATE:
            state["reservation_status"] = ReservationStatus.COLLECTING_DATES
            state["retry_count"] = 0
            state["response"] = ASK_DATES_MESSAGE
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=ASK_DATES_MESSAGE)
            ]
            return state

        # If dates already collected, skip
        if state["reservation_data"].start_time and state["reservation_data"].end_time:
            logger.info(f"Dates already collected: {state['reservation_data'].start_time} - {state['reservation_data'].end_time}")
            return state

        # Try to extract dates
        start_date, end_date = self.data_extractor.extract_dates(state["user_input"])

        if start_date and end_date:
            state["reservation_data"].start_time = start_date
            state["reservation_data"].end_time = end_date
            logger.info(f"Dates collected: {start_date} to {end_date}")
            state["retry_count"] = 0
            return state
        else:
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.warning(f"Failed to extract dates. Retry count: {state['retry_count']}")

            if state["retry_count"] >= self.MAX_RETRIES:
                state["response"] = \
                f"I'm having trouble understanding. "
                f"Let's start over or try a different question."
                state["reservation_status"] = ReservationStatus.CANCELLED
            else:
                state["response"] = INVALID_INPUT_MESSAGE.format(
                    context= \
                    f"Please provide start and end dates "
                    f"(e.g., 'from January 20th to January 25th' or 'tomorrow for 3 days')."
                )

            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]

            return state

    def _route_after_dates(
        self,
        state: ChatbotState
    ) -> Literal["next_field", "asked_question", "retry", "fail"]:
        """Route after dates collection"""
        if state["reservation_status"] == ReservationStatus.CANCELLED:
            return "fail"

        # Data collected → move to confirmation
        if state["reservation_data"].start_time and state["reservation_data"].end_time:
            return "next_field"

        # If we just asked the question (retry_count is 0 and no dates yet)
        if state.get("retry_count", 0) == 0 \
            and not (state["reservation_data"].start_time and state["reservation_data"].end_time):
            logger.info("Just asked for dates, ending invoke to wait for response")
            return "asked_question"

        return "retry"

    def _confirm_reservation(self, state: ChatbotState) -> ChatbotState:
        """Ask user to confirm collected data"""
        logger.info("Confirming reservation data...")

        # First time showing confirmation
        if state["reservation_status"] == ReservationStatus.COLLECTING_DATES:
            state["reservation_status"] = ReservationStatus.CONFIRMING
            state["retry_count"] = 0

            # Generate confirmation message using LLM
            prompt = PromptTemplate.from_template(CONFIRM_DATA_PROMPT)
            chain = prompt | self.rag_system.llm | StrOutputParser()

            data = state["reservation_data"]
            message = chain.invoke({
                "name": data.name,
                "surname": data.surname,
                "car_plate": data.car_plate,
                "start_date": data.start_time,
                "end_date": data.end_time
            })

            state["response"] = message
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=message)
            ]
            return state

        # User responded to confirmation
        user_input = state["user_input"].lower().strip()

        # Check for confirmation
        confirmation_words = ["yes", "correct", "confirm", "right", "ok", "okay", "sure", "yep", "yeah"]
        rejection_words = ["no", "wrong", "incorrect", "change", "fix", "nope"]

        if any(word in user_input for word in confirmation_words):
            logger.info("User confirmed reservation data")
            state["reservation_status"] = ReservationStatus.COMPLETED
            return state
        elif any(word in user_input for word in rejection_words):
            logger.info("User rejected reservation data")
            state["reservation_status"] = ReservationStatus.STARTED
            state["reservation_data"] = ReservationData()  # Reset data
            state["response"] = "No problem! Let's start over. What is your first name?"
            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]
            return state
        else:
            # Unclear response
            state["retry_count"] = state.get("retry_count", 0) + 1

            if state["retry_count"] >= self.MAX_RETRIES:
                state["response"] = "I'm having trouble understanding. Let's start over."
                state["reservation_status"] = ReservationStatus.CANCELLED
            else:
                state["response"] = "Please say 'yes' to confirm or 'no' if you'd like to make changes."

            state["messages"] = state.get("messages", []) + [
                HumanMessage(content=state["user_input"]),
                AIMessage(content=state["response"])
            ]

            return state

    def _route_after_confirmation(
        self,
        state: ChatbotState
    ) -> Literal["confirmed", "rejected", "fail"]:
        """Route after confirmation"""
        if state["reservation_status"] == ReservationStatus.COMPLETED:
            return "confirmed"
        elif state["reservation_status"] == ReservationStatus.STARTED:
            return "rejected"
        else:
            return "fail"

    def _finalize_reservation(self, state: ChatbotState) -> ChatbotState:
        """Finalize the reservation and prepare for admin approval"""
        logger.info("Finalizing reservation...")

        data = state["reservation_data"]
        conversation_id = state.get("conversation_id", "default")

        try:
            from api.reservation_manager import get_reservation_manager
            from api.reservation_models import ReservationCreate

            reservation_manager = get_reservation_manager()

            reservation_data = ReservationCreate(
                conversation_id=conversation_id,
                name=data.name,
                surname=data.surname,
                car_plate=data.car_plate,
                start_time=data.start_time,
                end_time=data.end_time
            )

            reservation = reservation_manager.create_reservation_sync(reservation_data)

            state["reservation_id"] = reservation.reservation_id
            state["reservation_status"] = ReservationStatus.PENDING_APPROVAL

            message = PENDING_APPROVAL_USER_MESSAGE.format(
                name=data.name,
                surname=data.surname,
                car_plate=data.car_plate,
                start_time=data.start_time,
                end_time=data.end_time,
                reservation_id=reservation.reservation_id
            )

            state["response"] = message
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=message)
            ]

            logger.info(
                f"Reservation created: {reservation.reservation_id} for "
                f"{data.name} {data.surname}, {data.car_plate}, "
                f"{data.start_time} - {data.end_time}. "
                f"User notified. Now proceeding to admin workflow."
            )

        except Exception as e:
            logger.error(f"Error creating reservation: {e}", exc_info=True)
            message = (
                f"Your reservation data has been collected:\n\n"
                f"Details:\n"
                f"Name: {data.name} {data.surname}\n"
                f"Car Plate: {data.car_plate}\n"
                f"Period: {data.start_time} to {data.end_time}\n\n"
                f"However, there was a technical issue submitting it for approval. "
                f"Please contact our support team."
            )
            state["reservation_status"] = ReservationStatus.CANCELLED

            state["response"] = message
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=message)
            ]

        return state

    def _format_for_admin(self, state: ChatbotState) -> ChatbotState:
        """
        Format reservation for admin review using LangChain LCEL
        LCEL Chain: PromptTemplate | LLM | StrOutputParser
        """
        logger.info("Formatting reservation for admin using LangChain...")

        from datetime import datetime

        prompt = PromptTemplate.from_template(ADMIN_REVIEW_PROMPT)
        chain = prompt | self.rag_system.llm | StrOutputParser()

        data = state["reservation_data"]
        reservation_id = state.get("reservation_id", "PENDING")

        formatted_message = chain.invoke({
            "reservation_id": reservation_id,
            "name": data.name,
            "surname": data.surname,
            "car_plate": data.car_plate,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        state["admin_review_message"] = formatted_message
        state["waiting_for_admin"] = True

        logger.info(f"Reservation {reservation_id} formatted for admin review")

        return state

    def _wait_for_admin_decision(self, state: ChatbotState) -> ChatbotState:
        """
        Wait for admin decision (interrupt point)
        This node is where the graph pauses for human input.
        Graph will resume when admin makes a decision via API.
        """
        logger.info("Waiting for admin decision...")

        reservation_id = state.get("reservation_id", "UNKNOWN")

        if state.get("admin_decision"):
            logger.info(
                f"Admin decision received for {reservation_id}: "
                f"{state['admin_decision']}"
            )
        else:
            logger.info(
                f"No admin decision yet for {reservation_id}, "
                f"graph will pause here (interrupt_before)"
            )
            state["waiting_for_admin"] = True

        return state

    def _route_after_admin_decision(
        self,
        state: ChatbotState
    ) -> Literal["approved", "rejected", "waiting"]:
        """Route based on admin decision"""

        decision = state.get("admin_decision")

        if decision == "approved":
            logger.info("Routing to approval processing")
            return "approved"
        elif decision == "rejected":
            logger.info("Routing to rejection processing")
            return "rejected"
        else:
            logger.info("Still waiting for admin decision")
            return "waiting"

    def _process_admin_approval(self, state: ChatbotState) -> ChatbotState:
        """
        Process admin approval using LangChain
        LCEL Chain: PromptTemplate | LLM | StrOutputParser
        """
        logger.info("Processing admin approval with LangChain...")

        data = state.get("reservation_data")
        if not data:
            logger.error("No reservation_data in state during approval")
            state["final_message"] = "Error: Reservation data not found"
            state["reservation_status"] = ReservationStatus.CANCELLED
            state["mcp_persisted"] = False
            return state

        prompt = PromptTemplate.from_template(ADMIN_APPROVAL_CONFIRMATION_PROMPT)
        chain = prompt | self.rag_system.llm | StrOutputParser()

        if isinstance(data, dict):
            name = data.get("name")
            surname = data.get("surname")
            car_plate = data.get("car_plate")
            start_time = data.get("start_time")
            end_time = data.get("end_time")
        else:
            name = getattr(data, "name", None)
            surname = getattr(data, "surname", None)
            car_plate = getattr(data, "car_plate", None)
            start_time = getattr(data, "start_time", None)
            end_time = getattr(data, "end_time", None)

        confirmation_message = chain.invoke({
            "name": name,
            "surname": surname,
            "car_plate": car_plate,
            "start_time": start_time,
            "end_time": end_time,
            "admin_comment": state.get("admin_comment", "Approved")
        })

        state["final_message"] = confirmation_message
        state["reservation_status"] = ReservationStatus.APPROVED

        logger.info(f"Admin approval processed for {state.get('reservation_id')}")

        return state

    def _process_admin_rejection(self, state: ChatbotState) -> ChatbotState:
        """
        Process admin rejection using LangChain
        LCEL Chain: PromptTemplate | LLM | StrOutputParser
        """
        logger.info("Processing admin rejection with LangChain...")

        data = state.get("reservation_data")
        if not data:
            logger.error("No reservation_data in state during rejection")
            state["final_message"] = "Error: Reservation data not found"
            state["reservation_status"] = ReservationStatus.CANCELLED
            return state

        prompt = PromptTemplate.from_template(ADMIN_REJECTION_MESSAGE_PROMPT)
        chain = prompt | self.rag_system.llm | StrOutputParser()

        if isinstance(data, dict):
            name = data.get("name")
        else:
            name = getattr(data, "name", None)

        rejection_message = chain.invoke({
            "name": name,
            "reason": state.get("admin_comment", "No reason provided")
        })

        state["final_message"] = rejection_message
        state["reservation_status"] = ReservationStatus.REJECTED

        logger.info(f"Admin rejection processed for {state.get('reservation_id')}")

        return state

    async def _persist_to_mcp_node(self, state: ChatbotState) -> ChatbotState:
        """Persist approved reservation to MCP (async node using MCP server)"""
        logger.info("Persisting to MCP as graph node...")

        try:
            reservation_data = state.get("reservation_data")
            if not reservation_data:
                logger.error("No reservation_data in state for MCP persistence")
                state["mcp_persisted"] = False
                state["mcp_error"] = "No reservation data"
                return state

            if isinstance(reservation_data, dict):
                name = reservation_data.get("name")
                surname = reservation_data.get("surname")
                car_plate = reservation_data.get("car_plate")
                start_time = reservation_data.get("start_time")
                end_time = reservation_data.get("end_time")
            else:
                name = getattr(reservation_data, "name", None)
                surname = getattr(reservation_data, "surname", None)
                car_plate = getattr(reservation_data, "car_plate", None)
                start_time = getattr(reservation_data, "start_time", None)
                end_time = getattr(reservation_data, "end_time", None)

            mcp_client = get_mcp_client()

            if not mcp_client.settings.MCP_ENABLED:
                logger.warning("MCP is disabled in settings, skipping persistence")
                state["mcp_persisted"] = False
                state["mcp_error"] = "MCP disabled"
                return state

            reservation_id = state.get("reservation_id", "UNKNOWN")

            try:
                logger.info(f"Writing reservation {reservation_id} to MCP server...")

                success = await mcp_client.write_confirmed_reservation(
                    name=name,
                    surname=surname,
                    car_plate=car_plate,
                    start_time=start_time,
                    end_time=end_time,
                    approval_time=datetime.now()
                )

                if success:
                    logger.info(
                        f"Reservation {reservation_id} persisted to MCP successfully"
                    )
                    state["mcp_persisted"] = True
                else:
                    logger.error(f"MCP write returned False for {reservation_id}")
                    state["mcp_persisted"] = False
                    state["mcp_error"] = "MCP write failed"

            except Exception as e:
                logger.error(f"Error writing to MCP: {e}", exc_info=True)
                state["mcp_persisted"] = False
                state["mcp_error"] = str(e)

        except Exception as e:
            logger.error(f"Error in MCP persistence node: {e}", exc_info=True)
            state["mcp_persisted"] = False
            state["mcp_error"] = str(e)

        return state

    def _notify_user_final(self, state: ChatbotState) -> ChatbotState:
        """Send final notification to user after admin decision"""
        logger.info("Sending final notification to user...")

        final_message = state.get(
            "final_message",
            "Your reservation has been processed."
        )

        if state["reservation_status"] == ReservationStatus.APPROVED:
            if state.get("mcp_persisted"):
                final_message += "\n\nYour reservation has been saved to our system."
            else:
                mcp_error = state.get("mcp_error", "Unknown error")
                logger.warning(
                    f"MCP persistence failed: {mcp_error}. "
                    f"User will still receive approval message."
                )

        state["response"] = final_message
        state["messages"] = state.get("messages", []) + [
            AIMessage(content=final_message)
        ]

        state["waiting_for_admin"] = False

        logger.info(
            f"Final notification sent. Status: {state['reservation_status']}"
        )

        return state
    
    async def chat_async(self, message: str, conversation_id: str = "default") -> str:
        logger.info(f"Processing message: {message}")
        config = {"configurable": {"thread_id": conversation_id}}        

        # Try to get existing state from checkpoint
        try:
            existing_state = self.graph.get_state(config)
            if existing_state and existing_state.values:
                # Update user input in existing state
                current_state = existing_state.values.copy()
                current_state["user_input"] = message
                logger.info(f"Continuing conversation with status: {current_state.get('reservation_status')}")
            else:
                # No existing state, create new one
                current_state = create_initial_state(user_input=message)
                current_state["conversation_id"] = conversation_id
                logger.info("Starting new conversation")
        except Exception as e:
            logger.warning(f"Could not retrieve existing state: {e}")
            current_state = create_initial_state(user_input=message)
            current_state["conversation_id"] = conversation_id

        result = await self.graph.ainvoke(current_state, config=config)  
        response = result.get("response", "I'm sorry, I couldn't process that.")
        logger.info("Message processed")
        return response

    def chat(self, message: str, conversation_id: str = "default") -> str:
        """Synchronous wrapper for chat_async"""
        try:
            loop = asyncio.get_running_loop()
            return asyncio.create_task(self.chat_async(message, conversation_id))
        except RuntimeError:
            return asyncio.run(self.chat_async(message, conversation_id))
    
    def get_conversation_history(self, conversation_id: str = "default") -> list:
        config = {"configurable": {"thread_id": conversation_id}}        
        try:
            state = self.graph.get_state(config)
            return state.values.get("messages", [])
        except:
            return []


def get_chatbot() -> ParkingChatbot:
    return ParkingChatbot()
