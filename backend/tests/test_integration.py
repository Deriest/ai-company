"""AIC-ADE Phase 3 — Integration Tests.

Tests for:
- Health endpoints
- Provider CRUD
- Conversation CRUD
- Security headers
- Validation
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db


@pytest.fixture
async def client():
    """Create test client."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================
# Health & Status Tests
# ============================================================

class TestHealthEndpoints:
    """Test health and status endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health endpoint returns ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


# ============================================================
# Provider Integration Tests
# ============================================================

class TestProviderIntegration:
    """Test provider CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_list_providers(self, client):
        """Test creating and listing providers."""
        # Create provider
        create_response = await client.post("/providers", json={
            "name": "Test Provider",
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
            "latencyMs": 0,
            "version": "1.0",
            "healthNotes": [],
            "models": []
        })
        assert create_response.status_code == 200
        provider = create_response.json()
        assert provider["name"] == "Test Provider"

        # List providers
        list_response = await client.get("/providers")
        assert list_response.status_code == 200
        providers = list_response.json()
        assert len(providers) >= 1

    @pytest.mark.asyncio
    async def test_update_provider(self, client):
        """Test updating provider."""
        # Create
        create_response = await client.post("/providers", json={
            "name": "Update Test",
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
            "latencyMs": 0,
            "version": "1.0"
        })
        assert create_response.status_code == 200
        provider_id = create_response.json()["id"]

        # Update
        update_response = await client.patch(f"/providers/{provider_id}", json={
            "name": "Updated Name"
        })
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_provider(self, client):
        """Test deleting provider."""
        # Create
        create_response = await client.post("/providers", json={
            "name": "Delete Test",
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
            "latencyMs": 0,
            "version": "1.0"
        })
        assert create_response.status_code == 200
        provider_id = create_response.json()["id"]

        # Delete
        delete_response = await client.delete(f"/providers/{provider_id}")
        assert delete_response.status_code == 200


# ============================================================
# Conversation Integration Tests
# ============================================================

class TestConversationIntegration:
    """Test conversation CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_list_conversations(self, client):
        """Test creating and listing conversations."""
        # Create
        create_response = await client.post("/conversations", json={
            "title": "Integration Test"
        })
        assert create_response.status_code == 200
        conv = create_response.json()
        assert conv["title"] == "Integration Test"

        # List
        list_response = await client.get("/conversations")
        assert list_response.status_code == 200

    @pytest.mark.asyncio
    async def test_conversation_messages(self, client):
        """Test adding messages to conversation."""
        # Create conversation
        conv_response = await client.post("/conversations", json={
            "title": "Message Test"
        })
        conv_id = conv_response.json()["id"]

        # Add message
        msg_response = await client.post(f"/conversations/{conv_id}/messages", json={
            "content": "Test message",
            "role": "user"
        })
        assert msg_response.status_code == 200
        assert msg_response.json()["content"] == "Test message"

        # Get messages
        get_response = await client.get(f"/conversations/{conv_id}/messages")
        assert get_response.status_code == 200
        messages = get_response.json()
        assert len(messages) >= 1


# ============================================================
# Error Handling Tests
# ============================================================

class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        """Test 404 handling."""
        response = await client.get("/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validation_error(self, client):
        """Test 422 handling."""
        response = await client.post("/providers", json={})
        assert response.status_code == 422


# ============================================================
# Localhost Security Tests
# ============================================================

class TestLocalhostSecurity:
    """Test localhost security."""

    @pytest.mark.asyncio
    async def test_security_headers(self, client):
        """Test security headers are present."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
