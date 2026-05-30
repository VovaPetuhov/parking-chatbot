import asyncio
import logging
from collections import OrderedDict
from datetime import datetime
from typing import List, Optional

from api.models import ConversationResponse, MessageHistory

logger = logging.getLogger(__name__)


class Session:
    """Single conversation session with message history"""
    
    def __init__(
        self, 
        conversation_id: str, 
        user_id: Optional[str] = None, 
        metadata: Optional[dict] = None
    ):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.messages: List[MessageHistory] = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.status = "active"
    
    def add_message(self, role: str, content: str) -> None:
        message = MessageHistory(
            role=role,
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_message_count(self) -> int:
        return len(self.messages)
    
    def is_expired(self, ttl_seconds: int) -> bool:
        age = datetime.now() - self.last_activity
        return age.total_seconds() > ttl_seconds
    
    def to_response(self) -> ConversationResponse:
        return ConversationResponse(
            conversation_id=self.conversation_id,
            created_at=self.created_at,
            last_activity=self.last_activity,
            message_count=self.get_message_count(),
            status=self.status
        )


class SessionManager:
    """
    Manages multiple conversation sessions with TTL and LRU cache.
    
    Features:
    - In-memory storage with OrderedDict for LRU
    - Automatic TTL expiration
    - Thread-safe with asyncio.Lock
    - Max sessions limit with LRU eviction
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 1000):
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.lock = asyncio.Lock()
        logger.info(
            f"SessionManager initialized (TTL: {ttl_seconds}s, Max sessions: {max_sessions})"
        )
    
    async def create_session(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Session:
        async with self.lock:
            # Check if session already exists
            if conversation_id in self.sessions:
                logger.warning(f"Session {conversation_id} already exists, returning existing")
                return self.sessions[conversation_id]
            
            # Enforce max sessions limit (LRU eviction)
            if len(self.sessions) >= self.max_sessions:
                oldest_id = next(iter(self.sessions))
                logger.info(f"Max sessions ({self.max_sessions}) reached, evicting oldest: {oldest_id}")
                self.sessions.pop(oldest_id)
            
            # Create new session
            session = Session(conversation_id, user_id, metadata)
            self.sessions[conversation_id] = session
            
            # Move to end (mark as most recently used)
            self.sessions.move_to_end(conversation_id)
            
            logger.info(f"Created session: {conversation_id}")
            return session
    
    async def get_session(self, conversation_id: str) -> Optional[Session]:
        async with self.lock:
            session = self.sessions.get(conversation_id)
            
            if session:
                if session.is_expired(self.ttl_seconds):
                    logger.info(f"Session {conversation_id} expired (TTL: {self.ttl_seconds}s), removing")
                    self.sessions.pop(conversation_id)
                    return None
                
                self.sessions.move_to_end(conversation_id)
            
            return session
    
    async def delete_session(self, conversation_id: str) -> bool:
        async with self.lock:
            if conversation_id in self.sessions:
                self.sessions.pop(conversation_id)
                logger.info(f"Deleted session: {conversation_id}")
                return True
            logger.warning(f"Session {conversation_id} not found for deletion")
            return False
    
    async def get_all_sessions(self) -> List[Session]:
        async with self.lock:
            await self._cleanup_expired()
            return list(self.sessions.values())
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> None:
        session = await self.get_session(conversation_id)
        if session:
            session.add_message(role, content)
            logger.debug(f"Added {role} message to session {conversation_id}")
        else:
            logger.warning(f"Cannot add message: session {conversation_id} not found")
    
    async def get_history(self, conversation_id: str) -> Optional[List[MessageHistory]]:
        session = await self.get_session(conversation_id)
        return session.messages if session else None
    
    async def _cleanup_expired(self) -> None:
        expired = [
            conv_id for conv_id, session in self.sessions.items()
            if session.is_expired(self.ttl_seconds)
        ]
        for conv_id in expired:
            self.sessions.pop(conv_id)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    async def cleanup_task(self) -> None:
        logger.info("Starting background cleanup task")
        while True:
            try:
                await asyncio.sleep(60)
                async with self.lock:
                    await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    def get_stats(self) -> dict:
        return {
            "total_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
            "ttl_seconds": self.ttl_seconds
        }


_session_manager: Optional[SessionManager] = None


def get_session_manager(ttl_seconds: int = 3600, max_sessions: int = 1000) -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(ttl_seconds, max_sessions)
    return _session_manager
