from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):    
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User message to send to chatbot"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation/session ID for context continuity"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "What are the working hours?",
                    "conversation_id": "user_123_session"
                }
            ]
        }
    }


class ChatResponse(BaseModel):    
    response: str = Field(..., description="Chatbot response message")
    conversation_id: str = Field(..., description="Conversation ID for this session")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "Our parking is open Monday-Friday 06:00-23:00...",
                    "conversation_id": "user_123_session",
                    "timestamp": "2024-01-15T10:30:00"
                }
            ]
        }
    }


class HealthResponse(BaseModel):    
    status: str = Field(..., description="API health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Health check timestamp"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "version": "1.0.0",
                    "timestamp": "2024-01-15T10:30:00"
                }
            ]
        }
    }
