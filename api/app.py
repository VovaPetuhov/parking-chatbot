import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.chatbot_adapter import get_chatbot_adapter
from api.models import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Parking Chatbot API",
    description="Reservation chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure from settings in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatbot_adapter = get_chatbot_adapter()


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Parking Chatbot API...")
    logger.info("Initializing chatbot...")
    try:
        # Pre-initialize chatbot on startup
        chatbot_adapter.get_instance()
        logger.info("Chatbot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize chatbot: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down Parking Chatbot API...")


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
    Args:
        request: ChatRequest containing message and optional conversation_id
    Returns:
        ChatResponse: Chatbot response with conversation_id and timestamp
    Raises:
        HTTPException: 500 if chatbot processing fails
    """
    try:
        logger.info(f"Received chat request: {request.message[:50]}...")
        conversation_id = request.conversation_id or f"conv_{datetime.now().timestamp()}"
        response = chatbot_adapter.send_message(
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
