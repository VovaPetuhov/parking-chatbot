import logging
from typing import Optional

from api.session_manager import get_session_manager
from graphs.chatbot_graph import ParkingChatbot, get_chatbot

logger = logging.getLogger(__name__)


class ChatbotAdapter:
    """
    Adapter for ParkingChatbot to provide API interface with session management.
    This adapter wraps the existing chatbot implementation, ensures singleton instance,
    and integrates with SessionManager for conversation history tracking.
    """
    _instance: Optional[ParkingChatbot] = None

    def __init__(self):
        self.session_manager = get_session_manager()
    
    @classmethod
    def get_instance(cls) -> ParkingChatbot:
        """
        Get singleton instance of chatbot.
        Returns:
            ParkingChatbot: Initialized chatbot instance
        """
        if cls._instance is None:
            logger.info("Initializing chatbot instance...")
            try:
                cls._instance = get_chatbot()
                logger.info("Chatbot initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize chatbot: {e}")
                raise
        return cls._instance
    
    async def send_message(self, message: str, conversation_id: str = "default") -> str:
        """
        Send message to chatbot and get response with history tracking.
        Args:
            message: User message
            conversation_id: Conversation/session identifier
        Returns:
            str: Chatbot response
        Raises:
            Exception: If chatbot processing fails
        """
        try:
            logger.debug(f"Processing message for conversation: {conversation_id}")

            # Ensure session exists
            session = await self.session_manager.get_session(conversation_id)
            if not session:
                logger.info(f"Auto-creating session for conversation: {conversation_id}")
                await self.session_manager.create_session(conversation_id)

            # Add user message to history
            await self.session_manager.add_message(conversation_id, "user", message)

            # Get chatbot response
            chatbot = self.get_chatbot_instance()
            response = chatbot.chat(message, conversation_id)

            # Add assistant response to history
            await self.session_manager.add_message(conversation_id, "assistant", response)

            logger.debug(f"Response generated for conversation: {conversation_id}")
            return response

        except Exception as e:
            logger.error(f"Error in chatbot processing: {e}", exc_info=True)
            raise
    
    @classmethod
    def get_chatbot_instance(cls) -> ParkingChatbot:
        return cls.get_instance()


def get_chatbot_adapter() -> ChatbotAdapter:
    return ChatbotAdapter()
