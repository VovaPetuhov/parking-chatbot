import logging
from typing import Optional

from graphs.chatbot_graph import ParkingChatbot, get_chatbot

logger = logging.getLogger(__name__)


class ChatbotAdapter:
    """
    Singleton adapter for ParkingChatbot to provide API interface.
    This adapter wraps the existing chatbot implementation and ensures
    only one instance is created for the entire application lifecycle.
    """
    
    _instance: Optional[ParkingChatbot] = None
    
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
    
    @classmethod
    def send_message(cls, message: str, conversation_id: str = "default") -> str:
        """
        Send message to chatbot and get response.
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
            chatbot = cls.get_instance()
            response = chatbot.chat(message, conversation_id)
            logger.debug(f"Response generated for conversation: {conversation_id}")
            return response
        except Exception as e:
            logger.error(f"Error in chatbot processing: {e}")
            raise
    
    @classmethod
    def get_conversation_history(cls, conversation_id: str = "default") -> list:
        """
        Get conversation history for a specific conversation.
        Args:
            conversation_id: Conversation/session identifier
        Returns:
            list: List of conversation messages
        """
        try:
            chatbot = cls.get_instance()
            history = chatbot.get_conversation_history(conversation_id)
            logger.debug(f"Retrieved {len(history)} messages for conversation: {conversation_id}")
            return history
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []


def get_chatbot_adapter() -> ChatbotAdapter:
    return ChatbotAdapter()
