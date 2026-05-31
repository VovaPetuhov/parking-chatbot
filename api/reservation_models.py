from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReservationStatusEnum(str, Enum):
    """Status of reservation approval process"""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ReservationBase(BaseModel):
    """Base reservation data"""
    name: str = Field(..., description="User's first name")
    surname: str = Field(..., description="User's last name")
    car_plate: str = Field(..., description="Car license plate number")
    start_time: str = Field(..., description="Reservation start date/time")
    end_time: str = Field(..., description="Reservation end date/time")


class ReservationCreate(ReservationBase):
    """Request model for creating reservation"""
    conversation_id: str = Field(..., description="Conversation ID from chat session")


class ReservationResponse(ReservationBase):
    """Response model for reservation"""
    reservation_id: str = Field(..., description="Unique reservation identifier")
    conversation_id: str = Field(..., description="Associated conversation ID")
    status: ReservationStatusEnum = Field(..., description="Current reservation status")
    created_at: datetime = Field(..., description="Reservation creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    admin_comment: Optional[str] = Field(None, description="Admin's comment on decision")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reservation_id": "res_abc123",
                    "conversation_id": "conv_xyz789",
                    "name": "John",
                    "surname": "Doe",
                    "car_plate": "ABC-123",
                    "start_time": "2024-01-20 10:00",
                    "end_time": "2024-01-25 18:00",
                    "status": "pending_approval",
                    "created_at": "2024-01-15T10:30:00",
                    "updated_at": "2024-01-15T10:30:00",
                    "admin_comment": None
                }
            ]
        }
    }


class ReservationApproval(BaseModel):
    """Request model for admin approval/rejection"""
    approved: bool = Field(..., description="True to approve, False to reject")
    comment: Optional[str] = Field(None, description="Optional admin comment")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "approved": True,
                    "comment": "Reservation approved"
                }
            ]
        }
    }


class ReservationListResponse(BaseModel):
    """Response model for list of reservations"""
    reservations: list[ReservationResponse] = Field(..., description="List of reservations")
    total: int = Field(..., description="Total number of reservations")
    pending: int = Field(..., description="Number of pending reservations")
    approved: int = Field(..., description="Number of approved reservations")
    rejected: int = Field(..., description="Number of rejected reservations")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reservations": [],
                    "total": 0,
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0
                }
            ]
        }
    }


class ReservationStatusResponse(BaseModel):
    """Response for checking reservation status"""
    reservation_id: str = Field(..., description="Reservation identifier")
    status: ReservationStatusEnum = Field(..., description="Current status")
    message: str = Field(..., description="Status message for user")
    admin_comment: Optional[str] = Field(None, description="Admin's comment if available")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reservation_id": "res_abc123",
                    "status": "pending_approval",
                    "message": "Your reservation is being reviewed by administrator",
                    "admin_comment": None
                }
            ]
        }
    }
