import asyncio

import pytest
from httpx import AsyncClient

from api.app import app


class TestAsyncConcurrentRequests:
    
    @pytest.mark.asyncio
    async def test_concurrent_chat_requests(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            tasks = [
                ac.post("/api/chat", json={"message": f"Test message {i}"})
                for i in range(5)
            ]
            responses = await asyncio.gather(*tasks)
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert "conversation_id" in data
                assert len(data["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_different_sessions(self):
        """Test concurrent requests to different conversation sessions"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            session1_response = await ac.post("/api/conversations", json={})
            session2_response = await ac.post("/api/conversations", json={})
            conv1_id = session1_response.json()["conversation_id"]
            conv2_id = session2_response.json()["conversation_id"]
            response1_task = ac.post(
                "/api/chat",
                json={"message": "Message for session 1", "conversation_id": conv1_id}
            )
            response2_task = ac.post(
                "/api/chat",
                json={"message": "Message for session 2", "conversation_id": conv2_id}
            )
            response1, response2 = await asyncio.gather(response1_task, response2_task)
            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response1.json()["conversation_id"] == conv1_id
            assert response2.json()["conversation_id"] == conv2_id
    
    @pytest.mark.asyncio
    async def test_concurrent_same_session(self):
        """Test concurrent requests to same session are handled correctly"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Create a session
            session_response = await ac.post("/api/conversations", json={})
            conv_id = session_response.json()["conversation_id"]
            tasks = [
                ac.post(
                    "/api/chat",
                    json={"message": f"Concurrent message {i}", "conversation_id": conv_id}
                )
                for i in range(3)
            ]
            responses = await asyncio.gather(*tasks)
            for response in responses:
                assert response.status_code == 200
                assert response.json()["conversation_id"] == conv_id
            history_response = await ac.get(f"/api/conversations/{conv_id}/history")
            assert history_response.status_code == 200
            history = history_response.json()
            assert history["message_count"] >= 6


class TestAsyncHealthEndpoints:
    
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            tasks = [ac.get("/api/health") for _ in range(10)]
            responses = await asyncio.gather(*tasks)
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self):
        """Test concurrent session creation and retrieval"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            create_tasks = [
                ac.post("/api/conversations", json={})
                for _ in range(5)
            ]
            create_responses = await asyncio.gather(*create_tasks)
            for response in create_responses:
                assert response.status_code == 201
            conv_ids = [resp.json()["conversation_id"] for resp in create_responses]
            get_tasks = [
                ac.get(f"/api/conversations/{conv_id}")
                for conv_id in conv_ids
            ]
            get_responses = await asyncio.gather(*get_tasks)
            for response in get_responses:
                assert response.status_code == 200


class TestAsyncErrorHandling:
    """Test async error handling"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_with_invalid_session(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            valid_session = (await ac.post("/api/conversations", json={})).json()
            valid_id = valid_session["conversation_id"]
            tasks = [
                ac.post("/api/chat", json={"message": "Valid", "conversation_id": valid_id}),
                ac.get("/api/conversations/invalid_id_1"),
                ac.get("/api/conversations/invalid_id_2"),
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=False)
            assert responses[0].status_code == 200
            assert responses[1].status_code == 404
            assert responses[2].status_code == 404
