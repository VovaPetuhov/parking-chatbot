import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.rag import get_rag_system
from graphs.state import ChatbotState, create_initial_state
from guardrails.pii_protection import get_guardrails_manager

logger = logging.getLogger(__name__)


class ParkingChatbot:
    """Main chatbot with LangGraph state machine"""
    
    def __init__(self):
        logger.info("Initializing Parking Chatbot...")
        self.rag_system = get_rag_system()
        self.guardrails = get_guardrails_manager()
        self.graph = self._build_graph()         
        logger.info("Parking Chatbot initialized")
    
    def _build_graph(self) -> StateGraph:        
        workflow = StateGraph(ChatbotState)
        # Add nodes
        workflow.add_node("check_guardrails", self._check_guardrails)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("handle_unsafe_input", self._handle_unsafe_input)
        # Add edges
        workflow.add_edge(START, "check_guardrails")
        workflow.add_conditional_edges(
            "check_guardrails",
            self._route_after_guardrails,
            {
                "safe": "retrieve_context",
                "unsafe": "handle_unsafe_input"
            }
        )
        workflow.add_edge("retrieve_context", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_unsafe_input", END)
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    def _check_guardrails(self, state: ChatbotState) -> ChatbotState:
        logger.info("Checking guardrails...")
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
    
    def _retrieve_context(self, state: ChatbotState) -> ChatbotState:
        logger.info("Retrieving context...")
        user_input = state["user_input"]
        docs = self.rag_system.retrieve_context(user_input)        
        filtered_docs = self.guardrails.filter_context(docs)        
        context = "\n\n".join([doc.page_content for doc in filtered_docs])
        state["retrieved_context"] = context
        logger.info(f"Retrieved {len(filtered_docs)} documents")
        return state
    
    def _generate_response(self, state: ChatbotState) -> ChatbotState:
        logger.info("Generating response...")
        user_input = state["user_input"]
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
    
    def chat(self, message: str, conversation_id: str = "default") -> str:
        logger.info(f"Processing message: {message}")
        initial_state = create_initial_state(user_input=message)        
        config = {"configurable": {"thread_id": conversation_id}}        
        result = self.graph.invoke(initial_state, config=config)  
        response = result.get("response", "I'm sorry, I couldn't process that.")
        logger.info("Message processed")
        return response
    
    def get_conversation_history(self, conversation_id: str = "default") -> list:
        config = {"configurable": {"thread_id": conversation_id}}        
        try:
            state = self.graph.get_state(config)
            return state.values.get("messages", [])
        except:
            return []


def get_chatbot() -> ParkingChatbot:
    return ParkingChatbot()
