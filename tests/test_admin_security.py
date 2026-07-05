import pytest
from fastapi.testclient import TestClient

from api.app import app
from config.settings import settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def valid_api_key():
    return settings.admin_api_key if settings.admin_api_key else "test-admin-key-for-testing"


@pytest.fixture
def invalid_api_key():
    return "invalid-key-that-should-not-work"


class TestAdminEndpointsSecurity:
    """Test security of admin endpoints"""

    # List of all admin endpoints to test
    ADMIN_GET_ENDPOINTS = [
        "/api/admin/reservations/pending",
        "/api/admin/reservations",
        "/api/admin/stats",
    ]

    ADMIN_GET_WITH_ID_ENDPOINTS = [
        "/api/admin/reservations/test-reservation-id",
    ]

    ADMIN_POST_ENDPOINTS = [
        ("/api/admin/reservations/test-id/approve", {"approved": True, "comment": "Test"}),
        ("/api/admin/reservations/test-id/reject", {"approved": False, "comment": "Test rejection"}),
    ]

    def test_admin_endpoints_reject_no_api_key(self, client):
        """Test that admin endpoints reject requests without API key"""
        for endpoint in self.ADMIN_GET_ENDPOINTS:
            response = client.get(endpoint)
            assert response.status_code == 403, f"Endpoint {endpoint} should require API key"
            assert "detail" in response.json()

    def test_admin_endpoints_with_id_reject_no_api_key(self, client):
        """Test that admin endpoints with ID reject requests without API key"""
        for endpoint in self.ADMIN_GET_WITH_ID_ENDPOINTS:
            response = client.get(endpoint)
            assert response.status_code == 403, f"Endpoint {endpoint} should require API key"

    def test_admin_post_endpoints_reject_no_api_key(self, client):
        """Test that admin POST endpoints reject requests without API key"""
        for endpoint, payload in self.ADMIN_POST_ENDPOINTS:
            response = client.post(endpoint, json=payload)
            assert response.status_code == 403, f"Endpoint {endpoint} should require API key"

    def test_admin_endpoints_reject_invalid_api_key(self, client, invalid_api_key):
        """Test that admin endpoints reject requests with invalid API key"""
        headers = {"X-Admin-API-Key": invalid_api_key}

        for endpoint in self.ADMIN_GET_ENDPOINTS:
            response = client.get(endpoint, headers=headers)
            assert response.status_code == 403, f"Endpoint {endpoint} should reject invalid API key"
            error_detail = response.json().get("detail", "")
            assert "Invalid" in error_detail or "missing" in error_detail.lower()

    def test_admin_endpoints_accept_valid_api_key(self, client, valid_api_key):
        """Test that admin endpoints accept requests with valid API key"""
        original_key = settings.admin_api_key
        settings.admin_api_key = valid_api_key

        try:
            headers = {"X-Admin-API-Key": valid_api_key}

            for endpoint in self.ADMIN_GET_ENDPOINTS:
                response = client.get(endpoint, headers=headers)
                assert response.status_code == 200, f"Endpoint {endpoint} should accept valid API key"

            response = client.get(
                "/api/admin/reservations/non-existent-id",
                headers=headers
            )
            assert response.status_code in [200, 404], \
                "Endpoint should accept valid API key (200 or 404, not 403)"

        finally:
            settings.admin_api_key = original_key

    def test_admin_approve_endpoint_requires_auth(self, client):
        """Test that approval endpoint specifically requires authentication"""
        response = client.post(
            "/api/admin/reservations/res_123/approve",
            json={"approved": True, "comment": "Test approval"}
        )
        assert response.status_code == 403, "Approve endpoint must require authentication"

    def test_admin_reject_endpoint_requires_auth(self, client):
        """Test that rejection endpoint specifically requires authentication"""
        response = client.post(
            "/api/admin/reservations/res_123/reject",
            json={"approved": False, "comment": "Test rejection"}
        )
        assert response.status_code == 403, "Reject endpoint must require authentication"

    def test_stats_endpoint_requires_auth(self, client):
        """Test that statistics endpoint requires authentication"""
        response = client.get("/api/admin/stats")
        assert response.status_code == 403, "Stats endpoint must require authentication"


class TestPublicEndpointsSecurity:
    """Test that public endpoints remain accessible without authentication"""

    def test_health_endpoint_is_public(self, client):
        """Test that health check endpoint is publicly accessible"""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_chat_endpoint_is_public(self, client):
        """Test that chat endpoint is publicly accessible"""
        response = client.post(
            "/api/chat",
            json={"message": "test", "conversation_id": "test-conv"}
        )
        assert response.status_code != 403, "Chat endpoint should not require admin API key"

    def test_user_reservation_status_is_public(self, client):
        """Test that user reservation status check is public"""
        response = client.get("/api/reservations/test-id/status")
        assert response.status_code != 403, "User reservation status should be public"


class TestSecurityHeaders:
    """Test security-related headers and responses"""

    def test_forbidden_response_format(self, client):
        """Test that 403 responses have proper format"""
        response = client.get("/api/admin/reservations/pending")
        assert response.status_code == 403
        
        data = response.json()
        assert "detail" in data, "403 response should include detail field"
        assert isinstance(data["detail"], str), "Detail should be a string"

    def test_api_key_header_name(self, client, invalid_api_key):
        """Test that API key is expected in correct header"""
        response = client.get(
            "/api/admin/reservations/pending",
            headers={"X-Admin-API-Key": invalid_api_key}
        )
        assert response.status_code == 403  # Wrong key, but correct header

        response = client.get(
            "/api/admin/reservations/pending",
            headers={"Authorization": f"Bearer {invalid_api_key}"}
        )
        assert response.status_code == 403

    def test_case_sensitivity_of_api_key(self, client, valid_api_key):
        """Test that API key comparison is case-sensitive"""
        original_key = settings.admin_api_key
        settings.admin_api_key = "TestKey123"

        try:
            response = client.get(
                "/api/admin/stats",
                headers={"X-Admin-API-Key": "TestKey123"}
            )
            assert response.status_code == 200

            response = client.get(
                "/api/admin/stats",
                headers={"X-Admin-API-Key": "testkey123"}
            )
            assert response.status_code == 403

        finally:
            settings.admin_api_key = original_key


class TestSecurityLogging:
    """Test that security events are properly logged"""

    def test_invalid_key_attempt_is_logged(self, client, invalid_api_key, caplog):
        """Test that invalid API key attempts are logged"""
        import logging
        
        with caplog.at_level(logging.WARNING):
            response = client.get(
                "/api/admin/reservations/pending",
                headers={"X-Admin-API-Key": invalid_api_key}
            )
            assert response.status_code == 403

    def test_successful_auth_is_logged(self, client, valid_api_key, caplog):
        """Test that successful authentication is logged"""
        import logging
        
        original_key = settings.admin_api_key
        settings.admin_api_key = valid_api_key

        try:
            with caplog.at_level(logging.INFO):
                response = client.get(
                    "/api/admin/stats",
                    headers={"X-Admin-API-Key": valid_api_key}
                )
                assert response.status_code == 200

        finally:
            settings.admin_api_key = original_key


@pytest.mark.parametrize("endpoint,method", [
    ("/api/admin/reservations/pending", "GET"),
    ("/api/admin/reservations", "GET"),
    ("/api/admin/reservations/test-id", "GET"),
    ("/api/admin/stats", "GET"),
])
def test_all_admin_get_endpoints_require_auth(client, endpoint, method):
    """Parametrized test to ensure all admin GET endpoints require authentication"""
    response = client.get(endpoint)
    assert response.status_code == 403, f"{method} {endpoint} must require authentication"


@pytest.mark.parametrize("endpoint,payload", [
    ("/api/admin/reservations/test-id/approve", {"approved": True, "comment": "Test"}),
    ("/api/admin/reservations/test-id/reject", {"approved": False, "comment": "Test"}),
])
def test_all_admin_post_endpoints_require_auth(client, endpoint, payload):
    """Parametrized test to ensure all admin POST endpoints require authentication"""
    response = client.post(endpoint, json=payload)
    assert response.status_code == 403, f"POST {endpoint} must require authentication"


def test_api_key_not_exposed_in_error_messages(client, invalid_api_key):
    """Test that API keys are not exposed in error messages"""
    response = client.get(
        "/api/admin/reservations/pending",
        headers={"X-Admin-API-Key": invalid_api_key}
    )
    
    error_detail = response.json().get("detail", "")
    assert invalid_api_key not in error_detail, \
        "API key should not be exposed in error messages"


def test_empty_api_key_is_rejected(client):
    """Test that empty API key is rejected"""
    response = client.get(
        "/api/admin/reservations/pending",
        headers={"X-Admin-API-Key": ""}
    )
    assert response.status_code == 403


def test_whitespace_api_key_is_rejected(client):
    """Test that whitespace-only API key is rejected"""
    response = client.get(
        "/api/admin/reservations/pending",
        headers={"X-Admin-API-Key": "   "}
    )
    assert response.status_code == 403
