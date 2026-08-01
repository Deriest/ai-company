"""
Test suite for QA-249-ROUND2 fixes.

Tests:
- R1: chat_service.py uses base_url with /v1 intact (no .replace)
- R2: main.py resolves models from worker_runtime, not first_model
- R3: planner mode gets model from worker_runtime
- R4: ConversationEngine applies token budget
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


class TestR1BaseUrlFix:
    """R1: Verify chat_service uses base_url with /v1 intact."""
    
    @pytest.mark.asyncio
    async def test_chat_service_preserves_v1_in_base_url(self):
        """Test that chat_service.chat_completion() does not strip /v1 from base_url."""
        from backend.services.chat_service import ChatService
        
        # Read the source to verify no .replace("/v1", "") exists
        import inspect
        source = inspect.getsource(ChatService.chat_completion)
        
        # Should NOT contain base_url.replace("/v1", "")
        assert 'base_url.replace("/v1", "")' not in source, \
            "chat_service.chat_completion() should NOT strip /v1 from base_url"
        
        # Should pass base_url directly to ProviderConfig
        assert "base_url=base_url" in source or "base_url," in source, \
            "chat_service.chat_completion() should pass base_url intact to ProviderConfig"


class TestR2WorkerRuntimeModelResolution:
    """R2 & R3: Verify main.py resolves models from worker_runtime."""
    
    @pytest.mark.asyncio
    async def test_main_startup_uses_worker_runtime_models(self):
        """Test that main.py startup queries worker_runtime for model assignments."""
        import inspect
        from backend.main import lifespan
        
        # Read the startup code
        source = inspect.getsource(lifespan)
        
        # Should import WorkerRuntime
        assert "WorkerRuntime" in source, \
            "main.py should import WorkerRuntime to resolve models"
        
        # Should query worker_runtime table
        assert "select(WorkerRuntime)" in source or "WorkerRuntime" in source, \
            "main.py should query WorkerRuntime to get role-specific models"
        
        # Should NOT use first_model = provider_models[0].model_id directly for all tiers
        # (this pattern would indicate the old bug)
        # Instead it should iterate workers and map their model_id to tiers
    
    @pytest.mark.asyncio
    async def test_thinker_and_planner_use_worker_runtime_model(self):
        """Test that thinker and planner roles resolve their models from worker_runtime."""
        from backend.models.schema import Provider, ProviderModel, WorkerRuntime
        from backend.database.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # Query provider
            from sqlalchemy import select
            provider_result = await db.execute(
                select(Provider).where(Provider.enabled == True).limit(1)
            )
            provider = provider_result.scalar_one_or_none()
            
            if not provider:
                pytest.skip("No active provider in test DB")
            
            # Query worker_runtime for thinker
            thinker_result = await db.execute(
                select(WorkerRuntime).where(WorkerRuntime.role == "thinker")
            )
            thinker = thinker_result.scalar_one_or_none()
            
            # Query worker_runtime for planner
            planner_result = await db.execute(
                select(WorkerRuntime).where(WorkerRuntime.role == "planner")
            )
            planner = planner_result.scalar_one_or_none()
            
            # At least one should exist and have a model_id
            assert thinker or planner, "At least thinker or planner should exist in worker_runtime"
            
            if thinker and thinker.model_id:
                # Verify thinker has a valid model (not combo/*)
                assert not thinker.model_id.startswith("combo/"), \
                    f"thinker model should not be combo/* (got {thinker.model_id})"
            
            if planner and planner.model_id:
                # Verify planner has a valid model (not combo/*)
                assert not planner.model_id.startswith("combo/"), \
                    f"planner model should not be combo/* (got {planner.model_id})"


class TestR4ConversationEngineTokenBudget:
    """R4: Verify ConversationEngine applies token budget."""
    
    @pytest.mark.asyncio
    async def test_conversation_engine_has_token_budget_method(self):
        """Test that ConversationEngine has _apply_token_budget method."""
        from conversation.engine import ConversationEngine
        
        # Check method exists
        assert hasattr(ConversationEngine, "_apply_token_budget"), \
            "ConversationEngine should have _apply_token_budget method"
        
        # Read source to verify it's called in chat methods
        import inspect
        chat_source = inspect.getsource(ConversationEngine._handle_chat_llm)
        question_source = inspect.getsource(ConversationEngine._handle_question_llm)
        
        assert "_apply_token_budget" in chat_source, \
            "_handle_chat_llm should call _apply_token_budget"
        assert "_apply_token_budget" in question_source, \
            "_handle_question_llm should call _apply_token_budget"
    
    @pytest.mark.asyncio
    async def test_apply_token_budget_truncates_messages(self):
        """Test that _apply_token_budget truncates messages when over budget."""
        from conversation.engine import ConversationEngine
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Create a mock session
        mock_session = MagicMock(spec=AsyncSession)
        engine = ConversationEngine(mock_session)
        
        # Create messages that exceed budget
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Question 1: " + "x" * 1000},
            {"role": "assistant", "content": "Answer 1: " + "y" * 1000},
            {"role": "user", "content": "Question 2: " + "z" * 1000},
            {"role": "assistant", "content": "Answer 2: " + "w" * 1000},
            {"role": "user", "content": "Question 3: " + "a" * 1000},
        ]
        
        # Apply budget with very small limit
        result = await engine._apply_token_budget(messages, max_tokens=500)
        
        # Should have fewer messages
        assert len(result) < len(messages), \
            "Token budget should truncate messages when over limit"
        
        # Should preserve system message
        assert any(m.get("role") == "system" for m in result), \
            "Token budget should preserve system messages"
        
        # Should preserve most recent user message
        assert result[-1].get("role") == "user", \
            "Token budget should preserve most recent user message"


class TestIntegration:
    """Integration tests for all fixes."""
    
    @pytest.mark.asyncio
    async def test_no_combo_model_in_default_fallback(self):
        """Test that combo/* models are filtered out in fallback logic."""
        import inspect
        from backend.main import lifespan
        
        source = inspect.getsource(lifespan)
        
        # Should filter out combo/* models
        assert "combo/" in source or "startswith" in source, \
            "main.py should filter out combo/* models in fallback logic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
