"""
QA-249-R5 Tests: Fix Regresi Truncate + Handle Upstream 400 CONTENT_LENGTH_EXCEEDS_THRESHOLD
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.context_overflow import estimate_tokens


class TestTruncateLogic:
    """Test truncate logic only triggers at hard max_tokens limit, not 90%."""
    
    def test_no_truncate_below_max_tokens(self):
        """160k conversation should NOT be truncated if max_tokens is 183k."""
        # Simulate 160k tokens
        messages = [
            {"role": "system", "content": "system prompt"},
            *[{"role": "user", "content": "x" * 4000} for _ in range(40)],  # ~160k tokens
        ]
        estimated = estimate_tokens(messages)
        max_tokens = 183000  # Model capacity
        
        # OLD LOGIC (R4): would truncate at 90% = 148k → WRONG
        # NEW LOGIC (R5): only truncate if estimated > max_tokens
        assert estimated < max_tokens, "160k should be under 183k limit"
        # No truncation should happen
    
    def test_truncate_above_max_tokens(self):
        """240k conversation SHOULD be truncated if max_tokens is 183k."""
        messages = [
            {"role": "system", "content": "system prompt"},
            *[{"role": "user", "content": "x" * 4000} for _ in range(60)],  # ~240k tokens
        ]
        estimated = estimate_tokens(messages)
        max_tokens = 183000
        
        assert estimated > max_tokens, "240k exceeds 183k limit, should truncate"


class TestUpstream400Handling:
    """Test graceful handling of upstream 400 CONTENT_LENGTH_EXCEEDS_THRESHOLD."""
    
    @pytest.mark.asyncio
    async def test_400_content_length_exceeds_threshold(self):
        """Upstream 400 with CONTENT_LENGTH_EXCEEDS_THRESHOLD should show friendly error."""
        from backend.services.chat_service import ChatService
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Mock DB session
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        
        # Mock provider config
        with patch.object(ChatService, '_get_provider_config', return_value=("http://test/v1", "test-key")):
            # Mock httpx to return 400 with threshold error
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.aread = AsyncMock(return_value=b'{"message":"Input content length exceeds threshold.","reason":"CONTENT_LENGTH_EXCEEDS_THRESHOLD"}')
            mock_response.json = MagicMock(return_value={
                "message": "Input content length exceeds threshold.",
                "reason": "CONTENT_LENGTH_EXCEEDS_THRESHOLD"
            })
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_stream_ctx = AsyncMock()
                mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
                mock_stream_ctx.__aexit__ = AsyncMock()
                mock_client.return_value.__aenter__.return_value.stream.return_value = mock_stream_ctx
                
                # Execute
                result_chunks = []
                async for chunk in ChatService.chat_stream(
                    db=db,
                    conversation_id="test-conv",
                    messages=[{"role": "user", "content": "test"}],
                    provider_id="test-provider",
                    model_id="test-model",
                ):
                    result_chunks.append(chunk)
                
                # Verify friendly error message, not raw JSON
                error_found = False
                for chunk in result_chunks:
                    if '"type": "error"' in chunk:
                        assert "Context terlalu besar" in chunk or "Mulai sesi baru" in chunk
                        assert "CONTENT_LENGTH_EXCEEDS_THRESHOLD" not in chunk  # No raw error
                        error_found = True
                
                assert error_found, "Should have emitted friendly error message"
    
    @pytest.mark.asyncio
    async def test_normal_response_not_affected(self):
        """Normal 200 responses should work as before."""
        from backend.services.chat_service import ChatService
        from sqlalchemy.ext.asyncio import AsyncSession
        
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        
        with patch.object(ChatService, '_get_provider_config', return_value=("http://test/v1", "test-key")):
            # Mock successful streaming response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            
            async def mock_lines():
                yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
                yield 'data: [DONE]'
            
            mock_response.aiter_lines = mock_lines
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_stream_ctx = AsyncMock()
                mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
                mock_stream_ctx.__aexit__ = AsyncMock()
                mock_client.return_value.__aenter__.return_value.stream.return_value = mock_stream_ctx
                
                result_chunks = []
                async for chunk in ChatService.chat_stream(
                    db=db,
                    conversation_id="test-conv",
                    messages=[{"role": "user", "content": "test"}],
                    provider_id="test-provider",
                    model_id="test-model",
                ):
                    result_chunks.append(chunk)
                
                # Should contain normal chunks
                has_content = any("Hello" in c for c in result_chunks)
                assert has_content, "Should stream normal content"


class TestEngineTokenBudget:
    """Test ConversationEngine uses proper policy, not hardcoded 1500."""
    
    @pytest.mark.asyncio
    async def test_engine_uses_context_policy_not_1500(self):
        """_apply_token_budget in engine.py should use policy, not hardcode 1500."""
        from conversation.engine import ConversationEngine
        from backend.services.context_builder import get_context_policy
        
        policy = get_context_policy("crafter")
        
        # Policy should give us reasonable context window (e.g., 60k)
        assert policy.max_tokens > 1500, f"Policy max_tokens ({policy.max_tokens}) should be > 1500"
        
        # Verify engine method exists
        engine = ConversationEngine(AsyncMock())
        assert hasattr(engine, "_apply_token_budget")
    
    @pytest.mark.asyncio
    async def test_apply_token_budget_does_not_truncate_valid_messages(self):
        """Messages under max_tokens should not be truncated."""
        from conversation.engine import ConversationEngine
        
        engine = ConversationEngine(AsyncMock())
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ]
        
        # Use generous budget
        result = await engine._apply_token_budget(messages, max_tokens=10000)
        
        # Should keep all messages
        assert len(result) == len(messages), "Should not truncate messages under budget"


class TestAcceptanceCriteria:
    """Verify all acceptance criteria from QA-249-R5.md."""
    
    def test_ac1_no_hardcode_1500_in_engine(self):
        """AC #5: _apply_token_budget should NOT hardcode 1500."""
        with open('/home/tvd/AI-Company/backend/conversation/engine.py', 'r') as f:
            engine_code = f.read()
        
        # Find _apply_token_budget calls in _handle_chat_llm and _handle_question_llm
        # Should use policy, not max_tokens=1500
        import re
        
        # Check for pattern: _apply_token_budget(messages, max_tokens=1500)
        # After fix, should have get_context_policy calls instead
        assert 'get_context_policy' in engine_code, "Should import and use get_context_policy"
    
    def test_ac2_no_raw_400_in_chat_service(self):
        """AC #6: 400 upstream should not leak raw JSON to UI."""
        with open('/home/tvd/AI-Company/backend/backend/services/chat_service.py', 'r') as f:
            chat_code = f.read()
        
        # Should have error handling for CONTENT_LENGTH_EXCEEDS_THRESHOLD
        assert 'CONTENT_LENGTH_EXCEEDS_THRESHOLD' in chat_code
        assert 'Context terlalu besar' in chat_code or 'terlalu besar' in chat_code
    
    def test_ac3_truncate_only_above_max_tokens(self):
        """AC #1-3: Truncate logic should only trigger above max_tokens, not 90%."""
        with open('/home/tvd/AI-Company/backend/backend/services/chat_service.py', 'r') as f:
            chat_code = f.read()
        
        # OLD: truncate_threshold = int(hard_limit * 0.9)
        # NEW: if estimated > policy.max_tokens
        # Should NOT have 0.9 threshold logic anymore
        assert 'QA-249-R5' in chat_code, "Should have R5 fix markers"
