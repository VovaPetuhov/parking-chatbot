import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import admin_routes, user_routes
from api.chatbot_adapter import get_chatbot_adapter
from api.models import (ChatRequest, ChatResponse, ConversationCreate,
                        ConversationDeleteResponse, ConversationHistory,
                        ConversationListResponse, ConversationResponse,
                        HealthResponse)
from api.reservation_manager import get_reservation_manager
from api.session_manager import get_session_manager
from config.settings import settings

logger = logging.getLogger(__name__)

session_manager = get_session_manager(
    ttl_seconds=settings.session_ttl_seconds,
    max_sessions=settings.max_sessions
)

chatbot_adapter = get_chatbot_adapter()

reservation_manager = get_reservation_manager(
    pending_ttl_seconds=getattr(settings, 'reservation_ttl_seconds', 3600),
    max_reservations=getattr(settings, 'max_reservations', 10000)
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Parking Chatbot API...")
    logger.info("Initializing chatbot...")
    try:
        chatbot_adapter.get_instance()
        logger.info("Chatbot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize chatbot: {e}")
        raise
    
    logger.info("Starting background cleanup tasks...")
    session_cleanup_task = asyncio.create_task(session_manager.cleanup_task())
    reservation_cleanup_task = asyncio.create_task(reservation_manager.cleanup_task())

    yield

    logger.info("Shutting down Parking Chatbot API...")
    logger.info("Stopping background tasks...")
    session_cleanup_task.cancel()
    reservation_cleanup_task.cancel()
    try:
        await session_cleanup_task
    except asyncio.CancelledError:
        logger.info("Session cleanup task cancelled successfully")
    try:
        await reservation_cleanup_task
    except asyncio.CancelledError:
        logger.info("Reservation cleanup task cancelled successfully")


app = FastAPI(
    title="Parking Chatbot API",
    description="Reservation chatbot with session management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=True)
async def root():
    """
    Root endpoint with API information.
    Returns basic information about the API and links to documentation.
    """
    return {
        "message": "Parking Chatbot API",
        "version": "1.0.0",
        "description": "Parking reservation chatbot",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Returns:
        HealthResponse: Health status information
    """
    logger.debug("Health check requested")
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send message to chatbot and receive response.
    Automatically creates or reuses conversation session.
    Args:
        request: ChatRequest containing message and optional conversation_id
    Returns:
        ChatResponse: Chatbot response with conversation_id and timestamp
    Raises:
        HTTPException: 500 if chatbot processing fails
    """
    try:
        logger.info(f"Received chat request: {request.message[:50]}...")
        conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        session = await session_manager.get_session(conversation_id)
        if not session:
            logger.info(f"Auto-creating session: {conversation_id}")
            await session_manager.create_session(conversation_id)

        response = await chatbot_adapter.send_message(
            message=request.message,
            conversation_id=conversation_id
        )
        logger.info(f"Response generated for conversation: {conversation_id}")
        return ChatResponse(
            response=response,
            conversation_id=conversation_id
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "type": type(exc).__name__
        }
    )


@app.post(
    "/api/conversations",
    response_model=ConversationResponse,
    status_code=201,
    tags=["Sessions"]
)
async def create_conversation(request: ConversationCreate):
    try:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        session = await session_manager.create_session(
            conversation_id=conversation_id,
            user_id=request.user_id,
            metadata=request.metadata
        )
        logger.info(f"Created new conversation: {conversation_id}")
        return session.to_response()

    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/conversations/{conversation_id}",
    response_model=ConversationResponse,
    tags=["Sessions"]
)
async def get_conversation(conversation_id: str):
    session = await session_manager.get_session(conversation_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or expired"
        )

    return session.to_response()


@app.get(
    "/api/conversations/{conversation_id}/history",
    response_model=ConversationHistory,
    tags=["Sessions"]
)
async def get_conversation_history(conversation_id: str):
    session = await session_manager.get_session(conversation_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or expired"
        )

    return ConversationHistory(
        conversation_id=session.conversation_id,
        messages=session.messages,
        created_at=session.created_at,
        last_activity=session.last_activity,
        message_count=session.get_message_count()
    )


@app.get(
    "/api/conversations",
    response_model=ConversationListResponse,
    tags=["Sessions"]
)
async def list_conversations():
    sessions = await session_manager.get_all_sessions()

    return ConversationListResponse(
        conversations=[s.to_response() for s in sessions],
        total=len(sessions),
        active=len([s for s in sessions if s.status == "active"])
    )


@app.delete(
    "/api/conversations/{conversation_id}",
    response_model=ConversationDeleteResponse,
    tags=["Sessions"]
)
async def delete_conversation(conversation_id: str):
    deleted = await session_manager.delete_session(conversation_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    return ConversationDeleteResponse(
        conversation_id=conversation_id,
        status="deleted",
        message=f"Conversation {conversation_id} deleted successfully"
    )


@app.post(
    "/api/conversations/{conversation_id}/reset",
    response_model=ConversationDeleteResponse,
    tags=["Sessions"]
)
async def reset_conversation(conversation_id: str):
    await session_manager.delete_session(conversation_id)
    await session_manager.create_session(conversation_id)

    return ConversationDeleteResponse(
        conversation_id=conversation_id,
        status="reset",
        message=f"Conversation {conversation_id} reset successfully"
    )


app.include_router(admin_routes.router)
app.include_router(user_routes.router)
