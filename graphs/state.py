"""
Reservation State - Data models for reservation process
"""
from datetime import datetime
from enum import Enum
from typing import Annotated, List, Optional

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ReservationStatus(str, Enum):
    """Status of reservation process"""
    STARTED = "started"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_SURNAME = "collecting_surname"
    COLLECTING_CAR_PLATE = "collecting_car_plate"
    COLLECTING_START_TIME = "collecting_start_time"
    COLLECTING_END_TIME = "collecting_end_time"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReservationData(BaseModel):
    """Data collected for reservation"""
    name: Optional[str] = None
    surname: Optional[str] = None
    car_plate: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if all required data is collected"""
        return all([
            self.name,
            self.surname,
            self.car_plate,
            self.start_time,
            self.end_time
        ])


class ChatbotState(TypedDict):
    messages: Annotated[List[AnyMessage], "Conversation history"]
    user_input: str
    reservation_status: ReservationStatus
    reservation_data: ReservationData
    retrieved_context: Optional[str]
    input_safe: bool
    guardrails_report: Optional[dict]
    response: str
    conversation_id: Optional[str]
    user_id: Optional[str] 


def create_initial_state(
    user_input: str,
    conversation_id: Optional[str] = None,
    messages: Optional[List[AnyMessage]] = None
) -> ChatbotState:
    return ChatbotState(
        messages=messages or [],
        user_input=user_input,
        reservation_status=ReservationStatus.STARTED,
        reservation_data=ReservationData(),
        retrieved_context=None,
        input_safe=True,
        guardrails_report=None,
        response="",
        conversation_id=conversation_id,
        user_id=None
    )
