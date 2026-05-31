import asyncio
from datetime import datetime, timedelta

import pytest

from api.models import ConversationResponse
from api.session_manager import Session, SessionManager, get_session_manager


class TestSession:
    
    def test_session_creation(self):
        session = Session("test_conv_1", user_id="user_123")
        assert session.conversation_id == "test_conv_1"
        assert session.user_id == "user_123"
        assert session.status == "active"
        assert len(session.messages) == 0
        assert session.get_message_count() == 0
    
    def test_add_message(self):
        session = Session("test_conv_2")
        session.add_message("user", "Hello")
        assert session.get_message_count() == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello"
        session.add_message("assistant", "Hi there!")
        assert session.get_message_count() == 2
        assert session.messages[1].role == "assistant"
    
    def test_session_expiration(self):
        """Test session expiration logic"""
        session = Session("test_conv_3")
        assert not session.is_expired(ttl_seconds=3600)
        session.last_activity = datetime.now() - timedelta(seconds=7200)
        assert session.is_expired(ttl_seconds=3600)
    
    def test_to_response(self):
        session = Session("test_conv_4", user_id="user_456")
        session.add_message("user", "Test message")
        response = session.to_response()
        assert isinstance(response, ConversationResponse)
        assert response.conversation_id == "test_conv_4"
        assert response.message_count == 1
        assert response.status == "active"


class TestSessionManager:

    @pytest.mark.asyncio
    async def test_create_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        session = await sm.create_session("conv_1", user_id="user_1")
        assert session is not None
        assert session.conversation_id == "conv_1"
        assert session.user_id == "user_1"
        assert len(sm.sessions) == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_session_creation(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        session1 = await sm.create_session("conv_dup")
        session2 = await sm.create_session("conv_dup")
        assert session1 is session2
        assert len(sm.sessions) == 1
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        await sm.create_session("conv_get")
        retrieved = await sm.get_session("conv_get")
        assert retrieved is not None
        assert retrieved.conversation_id == "conv_get"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        session = await sm.get_session("nonexistent_conv")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_delete_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        await sm.create_session("conv_del")
        deleted = await sm.delete_session("conv_del")
        assert deleted is True
        assert len(sm.sessions) == 0
        session = await sm.get_session("conv_del")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        deleted = await sm.delete_session("nonexistent")
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_add_message_to_session(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        await sm.create_session("conv_msg")
        await sm.add_message("conv_msg", "user", "Hello")
        await sm.add_message("conv_msg", "assistant", "Hi")
        session = await sm.get_session("conv_msg")
        assert session.get_message_count() == 2
    
    @pytest.mark.asyncio
    async def test_get_history(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        await sm.create_session("conv_hist")
        await sm.add_message("conv_hist", "user", "Message 1")
        await sm.add_message("conv_hist", "assistant", "Response 1")
        history = await sm.get_history("conv_hist")
        assert history is not None
        assert len(history) == 2
        assert history[0].content == "Message 1"
        assert history[1].content == "Response 1"
    
    @pytest.mark.asyncio
    async def test_get_all_sessions(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        await sm.create_session("conv_all_1")
        await sm.create_session("conv_all_2")
        await sm.create_session("conv_all_3")
        all_sessions = await sm.get_all_sessions()
        assert len(all_sessions) == 3
    
    @pytest.mark.asyncio
    async def test_session_ttl_expiration(self):
        sm = SessionManager(ttl_seconds=1, max_sessions=100)
        await sm.create_session("conv_ttl")
        session = await sm.get_session("conv_ttl")
        assert session is not None
        await asyncio.sleep(2)
        session = await sm.get_session("conv_ttl")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_lru_max_sessions_eviction(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=3)
        await sm.create_session("conv_lru_1")
        await sm.create_session("conv_lru_2")
        await sm.create_session("conv_lru_3")
        assert len(sm.sessions) == 3
        await sm.create_session("conv_lru_4")
        assert len(sm.sessions) == 3
        assert await sm.get_session("conv_lru_1") is None
        assert await sm.get_session("conv_lru_2") is not None
        assert await sm.get_session("conv_lru_3") is not None
        assert await sm.get_session("conv_lru_4") is not None
    
    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=3)
        await sm.create_session("conv_order_1")
        await sm.create_session("conv_order_2")
        await sm.create_session("conv_order_3")
        await sm.get_session("conv_order_1")
        await sm.create_session("conv_order_4")
        assert await sm.get_session("conv_order_1") is not None
        assert await sm.get_session("conv_order_2") is None
        assert await sm.get_session("conv_order_3") is not None
        assert await sm.get_session("conv_order_4") is not None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        sm = SessionManager(ttl_seconds=1, max_sessions=100)
        await sm.create_session("conv_clean_1")
        await sm.create_session("conv_clean_2")
        await asyncio.sleep(2)
        await sm._cleanup_expired()
        assert len(sm.sessions) == 0
    
    def test_get_stats(self):
        sm = SessionManager(ttl_seconds=1800, max_sessions=500)
        stats = sm.get_stats()
        assert stats["ttl_seconds"] == 1800
        assert stats["max_sessions"] == 500
        assert stats["total_sessions"] == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self):
        sm = SessionManager(ttl_seconds=3600, max_sessions=100)
        tasks = [
            sm.create_session(f"conv_concurrent_{i}")
            for i in range(10)
        ]
        await asyncio.gather(*tasks)
        assert len(sm.sessions) == 10


class TestSessionManagerSingleton:
    
    def test_singleton_instance(self):
        import api.session_manager as sm_module
        sm_module._session_manager = None
        sm1 = get_session_manager(ttl_seconds=1000, max_sessions=100)
        sm2 = get_session_manager(ttl_seconds=2000, max_sessions=200)
        assert sm1 is sm2
        assert sm1.ttl_seconds == 1000
        assert sm1.max_sessions == 100
