"""AIC-ADE — Context Inspection API Tests."""

import pytest


class TestContextInspectionAPI:
    """Test context inspection API endpoints."""

    def test_assemble_endpoint_exists(self):
        """Test that assemble endpoint exists."""
        from backend.routes.context import assemble_context
        assert callable(assemble_context)

    def test_sources_endpoint_exists(self):
        """Test that sources endpoint exists."""
        from backend.routes.context import get_sources
        assert callable(get_sources)
