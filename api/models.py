from datetime import datetime
from typing import List, Optional

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


class ConversationCreate(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Optional - user identifier"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user_123",
                    "metadata": {"source": "web", "platform": "desktop"}
                }
            ]
        }
    }


class ConversationResponse(BaseModel):
    conversation_id: str = Field(..., description="Unique conversation identifier")
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    message_count: int = Field(..., description="Total number of messages in session")
    status: str = Field(default="active", description="Session status: active, expired, deleted")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv_abc123",
                    "created_at": "2024-01-15T10:00:00",
                    "last_activity": "2024-01-15T10:30:00",
                    "message_count": 5,
                    "status": "active"
                }
            ]
        }
    }


class MessageHistory(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "role": "user",
                    "content": "What are the working hours?",
                    "timestamp": "2024-01-15T10:30:00"
                }
            ]
        }
    }


class ConversationHistory(BaseModel):
    conversation_id: str = Field(..., description="Conversation identifier")
    messages: List[MessageHistory] = Field(..., description="List of messages")
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    message_count: int = Field(..., description="Total message count")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv_abc123",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Hello",
                            "timestamp": "2024-01-15T10:00:00"
                        },
                        {
                            "role": "assistant",
                            "content": "Hi! How can I help?",
                            "timestamp": "2024-01-15T10:00:05"
                        }
                    ],
                    "created_at": "2024-01-15T10:00:00",
                    "last_activity": "2024-01-15T10:00:05",
                    "message_count": 2
                }
            ]
        }
    }


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")
    active: int = Field(..., description="Number of active conversations")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversations": [],
                    "total": 0,
                    "active": 0
                }
            ]
        }
    }


class ConversationDeleteResponse(BaseModel):
    conversation_id: str = Field(..., description="Deleted conversation ID")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Status message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "con_123",
                    "status": "deleted",
                    "message": "Conversation con_123 deleted successfully"
                }
            ]
        }
    }
