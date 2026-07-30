"""AIC-ADE — Chat Service Context Integration Tests."""

import pytest
from backend.services.chat_service import build_chat_context


class TestBuildChatContext:
    """Test build_chat_context function."""

    @pytest.mark.asyncio
    async def test_function_exists(self):
        """Test that build_chat_context function exists."""
        assert callable(build_chat_context)

    @pytest.mark.asyncio
    async def test_returns_string(self):
        """Test that function returns string."""
        # With None db, should return empty string (graceful fallback)
        result = await build_chat_context(None, "conv-1", "test query")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Test that function handles errors gracefully."""
        # With invalid db, should return empty string
        result = await build_chat_context("invalid", "conv-1", "test query")
        assert isinstance(result, str)
