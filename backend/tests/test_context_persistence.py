"""AIC-ADE — Context Persistence Tests."""

import pytest
from context.pipeline import ContextAssembly, ContextPipeline


class TestContextAssemblyPersistence:
    """Test ContextAssembly persistence."""

    def test_assembly_has_id_field(self):
        assembly = ContextAssembly()
        assert assembly.id is None

    def test_assembly_id_set(self):
        assembly = ContextAssembly()
        assembly.id = "test-id"
        assert assembly.id == "test-id"


class TestPipelinePersistence:
    """Test pipeline persist method."""

    @pytest.mark.asyncio
    async def test_persist_method_exists(self):
        pipeline = ContextPipeline()
        assert hasattr(pipeline, 'persist')

    @pytest.mark.asyncio
    async def test_persist_assembly(self):
        # This test verifies the persist method signature
        # Actual DB tests would require database setup
        pipeline = ContextPipeline()
        assembly = ContextAssembly(
            sources_used=["memory"],
            total_tokens=100,
            token_budget=4000,
            metadata={"query": "test"},
        )
        # Just verify the method exists and can be called
        # Real DB tests would be in integration tests
        assert callable(pipeline.persist)
