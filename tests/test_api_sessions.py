from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


class TestConversationEndpoints:
    """Test conversation management endpoints"""
    
    def test_create_conversation_minimal(self):
        response = client.post("/api/conversations", json={})
        assert response.status_code == 201
        data = response.json()
        assert "conversation_id" in data
        assert data["conversation_id"].startswith("conv_")
        assert data["status"] == "active"
        assert data["message_count"] == 0
        assert "created_at" in data
        assert "last_activity" in data
    
    def test_create_conversation_with_metadata(self):
        payload = {
            "user_id": "test_user_123",
            "metadata": {
                "source": "web",
                "platform": "desktop"
            }
        }
        
        response = client.post("/api/conversations", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "conversation_id" in data
    
    def test_get_conversation_success(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        response = client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["status"] == "active"
    
    def test_get_conversation_not_found(self):
        response = client.get("/api/conversations/nonexistent_conv_id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_list_conversations_empty(self):
        response = client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert "total" in data
        assert "active" in data
        assert isinstance(data["conversations"], list)
    
    def test_list_conversations_with_sessions(self):
        conv_ids = []
        for _ in range(3):
            create_response = client.post("/api/conversations", json={})
            conv_ids.append(create_response.json()["conversation_id"])
        response = client.get("/api/conversations")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        listed_ids = [conv["conversation_id"] for conv in data["conversations"]]
        for conv_id in conv_ids:
            assert conv_id in listed_ids
    
    def test_delete_conversation_success(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        response = client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["status"] == "deleted"
        get_response = client.get(f"/api/conversations/{conv_id}")
        assert get_response.status_code == 404
    
    def test_delete_conversation_not_found(self):
        response = client.delete("/api/conversations/nonexistent_conv")
        assert response.status_code == 404
    
    def test_reset_conversation(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        client.post("/api/chat", json={
            "message": "Test message",
            "conversation_id": conv_id
        })
        response = client.post(f"/api/conversations/{conv_id}/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["status"] == "reset"
        history_response = client.get(f"/api/conversations/{conv_id}/history")
        assert history_response.json()["message_count"] == 0


class TestChatWithSessions:
    def test_chat_auto_creates_session(self):
        response = client.post("/api/chat", json={
            "message": "Hello"
        })
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "response" in data
    
    def test_chat_with_existing_session(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        response = client.post("/api/chat", json={
            "message": "What are the working hours?",
            "conversation_id": conv_id
        })
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert len(data["response"]) > 0
    
    def test_chat_persistent_context(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        response1 = client.post("/api/chat", json={
            "message": "Hello",
            "conversation_id": conv_id
        })
        assert response1.status_code == 200
        response2 = client.post("/api/chat", json={
            "message": "What are the prices?",
            "conversation_id": conv_id
        })
        assert response2.status_code == 200
        assert response2.json()["conversation_id"] == conv_id


class TestConversationHistory:
    
    def test_get_history_empty(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        response = client.get(f"/api/conversations/{conv_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["message_count"] == 0
        assert len(data["messages"]) == 0
    
    def test_get_history_with_messages(self):
        create_response = client.post("/api/conversations", json={})
        conv_id = create_response.json()["conversation_id"]
        client.post("/api/chat", json={
            "message": "First message",
            "conversation_id": conv_id
        })
        client.post("/api/chat", json={
            "message": "Second message",
            "conversation_id": conv_id
        })
        response = client.get(f"/api/conversations/{conv_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["message_count"] >= 2
        assert len(data["messages"]) >= 2
        for msg in data["messages"]:
            assert "role" in msg
            assert "content" in msg
            assert "timestamp" in msg
            assert msg["role"] in ["user", "assistant"]
    
    def test_get_history_not_found(self):
        """Test getting history of non-existent conversation"""
        response = client.get("/api/conversations/nonexistent_conv/history")
        
        assert response.status_code == 404


class TestSessionIsolation:
    
    def test_parallel_conversations_isolated(self):
        """Test that multiple conversations maintain separate context"""
        conv1_response = client.post("/api/conversations", json={})
        conv1_id = conv1_response.json()["conversation_id"]
        conv2_response = client.post("/api/conversations", json={})
        conv2_id = conv2_response.json()["conversation_id"]
        client.post("/api/chat", json={
            "message": "Message for conversation 1",
            "conversation_id": conv1_id
        })
        client.post("/api/chat", json={
            "message": "Message for conversation 2",
            "conversation_id": conv2_id
        })
        hist1 = client.get(f"/api/conversations/{conv1_id}/history").json()
        hist2 = client.get(f"/api/conversations/{conv2_id}/history").json()
        assert hist1["conversation_id"] != hist2["conversation_id"]
        assert hist1["conversation_id"] == conv1_id
        assert hist2["conversation_id"] == conv2_id
        conv1_content = [msg["content"] for msg in hist1["messages"]]
        conv2_content = [msg["content"] for msg in hist2["messages"]]
        assert any("conversation 1" in content for content in conv1_content)
        assert any("conversation 2" in content for content in conv2_content)


class TestAPIValidation:
    
    def test_chat_empty_message(self):
        response = client.post("/api/chat", json={
            "message": ""
        })
        assert response.status_code == 422
    
    def test_chat_too_long_message(self):
        response = client.post("/api/chat", json={
            "message": "x" * 1001  # max_length=1000
        })
        assert response.status_code == 422
    
    def test_chat_missing_message(self):
        response = client.post("/api/chat", json={})
        assert response.status_code == 422


class TestHealthCheck:
    
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestRootEndpoint:
    
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
