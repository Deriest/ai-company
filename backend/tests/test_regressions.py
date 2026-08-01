"""Regression coverage for defects found in the v2.4.6+ full-explore QA."""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import backend.migrations.runner as migration_runner
from backend.database.session import engine as backend_engine
from backend.services.tool_chat_service import ToolAwareChatService
from backend.services.context_builder import WorkerContext, ContextPolicy
from llm.provider import provider_manager
from storage.models import Message


class _ProviderStub:
    async def chat(self, **_kwargs):
        return {"content": "Tool chat is available."}


@pytest.mark.asyncio
async def test_tool_chat_uses_module_model_tier_when_provider_is_active(monkeypatch):
    """BUG-01: a registered provider must not shadow ModelTier as a local."""
    monkeypatch.setattr(provider_manager, "get_active", lambda: _ProviderStub())

    service = ToolAwareChatService()
    events = [event async for event in service.stream_with_tools([{"role": "user", "content": "hello"}])]

    assert any(json.loads(event.removeprefix("data: "))["type"] == "chunk" for event in events)
    assert not any("UnboundLocalError" in event for event in events)


def test_canonical_message_supports_primary_api_metadata_alias_and_timestamps():
    """BUG-02: primary routes use the storage mapper and retain API metadata."""
    message = Message(conversation_id="conversation", role="assistant", content="response", message_metadata={"source": "test"})

    assert message.meta == {"source": "test"}
    assert message.message_metadata == {"source": "test"}
    assert Message.created_at.default is not None


@pytest.mark.asyncio
async def test_timestamp_migration_repairs_legacy_null_messages(monkeypatch):
    """BUG-02: existing failed streams must not permanently break history."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with test_engine.begin() as connection:
            await connection.execute(text("CREATE TABLE messages (created_at DATETIME, updated_at DATETIME)"))
            await connection.execute(text("CREATE TABLE conversations (created_at DATETIME, updated_at DATETIME)"))
            await connection.execute(text("INSERT INTO messages VALUES (NULL, '2026-07-31 14:08:26')"))
            await connection.execute(text("INSERT INTO conversations VALUES (NULL, NULL)"))

        monkeypatch.setattr(migration_runner, "engine", test_engine)
        # Find the timestamp repair migration by name (not by index, as migrations may be added)
        timestamp_migration = next(
            (m for m in migration_runner.MIGRATIONS if m["name"] == "repair_conversation_timestamps"),
            None
        )
        assert timestamp_migration is not None, "repair_conversation_timestamps migration not found"
        monkeypatch.setattr(migration_runner, "MIGRATIONS", [timestamp_migration])
        await migration_runner.run_migrations()

        async with test_engine.connect() as connection:
            message = (await connection.execute(text("SELECT created_at, updated_at FROM messages"))).one()
            conversation = (await connection.execute(text("SELECT created_at, updated_at FROM conversations"))).one()

        assert message.created_at is not None
        assert message.updated_at is not None
        assert conversation.created_at is not None
        assert conversation.updated_at is not None
    finally:
        monkeypatch.setattr(migration_runner, "engine", backend_engine)
        await test_engine.dispose()


# ── BUG-06: Provider SSE parsing ──────────────────────────────────────────

def _make_sse_response(sse_lines: list[str]) -> object:
    """Build a mock httpx response with SSE body text."""
    import types
    text_body = "\n".join(f"data: {line}" for line in sse_lines)
    resp = types.SimpleNamespace()
    resp.text = text_body
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json = lambda: (_ for _ in ()).throw(json.JSONDecodeError("SSE not JSON", "", 0))
    return resp


@pytest.mark.asyncio
async def test_provider_chat_parses_sse_response_when_json_fails(monkeypatch):
    """BUG-06: provider.chat() must parse SSE data: lines when resp.json() fails."""
    from llm.provider import LLMProvider, ProviderConfig

    config = ProviderConfig(name="test-sse", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    sse_lines = [
        '{"choices":[{"delta":{"content":"Hello"},"index":0}]}',
        '{"choices":[{"delta":{"content":" world"},"index":0}]}',
        '{"choices":[{"delta":{"content":""},"index":0}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}',
    ]
    resp = _make_sse_response(sse_lines)

    async def mock_post(*args, **kwargs):
        return resp

    monkeypatch.setattr(provider.client, "post", mock_post)

    result = await provider.chat(messages=[{"role": "user", "content": "hi"}])
    assert result["content"] == "Hello world"  # merged from SSE chunks
    assert result["model"] is not None


@pytest.mark.asyncio
async def test_provider_chat_sse_empty_body_raises_actionable_error(monkeypatch):
    """BUG-06+08: empty body must include model and URL in error message."""
    from llm.provider import LLMProvider, ProviderConfig, LLMError

    config = ProviderConfig(name="test-empty", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    class _EmptyResp:
        text = ""
        status_code = 200
        raise_for_status = lambda self: None

    async def mock_post(*args, **kwargs):
        return _EmptyResp()

    monkeypatch.setattr(provider.client, "post", mock_post)

    with pytest.raises(LLMError) as exc:
        await provider.chat(messages=[{"role": "user", "content": "hi"}])
    msg = str(exc.value)
    assert "Empty LLM response body" in msg
    assert "kr/claude" in msg or "test/v1" in msg


# ── BUG-07: Token-budget trimming ─────────────────────────────────────────

def test_context_to_messages_trims_by_token_budget():
    """BUG-07: to_messages() must drop oldest non-system messages when over budget."""
    policy = ContextPolicy(
        max_history=50,
        max_files=5,
        max_tokens=100,    # very tight budget
        response_tokens=50,
        summarization="minimal",
        retrieval_first=False,
    )

    # Build a context with one large message that exceeds the budget
    ctx = WorkerContext(
        system_prompt="Short system prompt",
        recent_messages=[
            {"role": "user", "content": "A" * 500},   # ~162 tokens with 1.3x buffer
            {"role": "assistant", "content": "B" * 500},
        ],
    )

    messages, metadata = ctx.to_messages(policy=policy)

    # With a 100-token budget, the two large messages should be dropped
    assert metadata["truncated"] is True
    assert metadata["dropped_messages"] > 0
    assert metadata["estimated_tokens"] <= metadata["max_tokens_budget"]


def test_context_to_messages_preserves_all_within_budget():
    """BUG-07: messages within budget are not truncated."""
    policy = ContextPolicy(
        max_history=50,
        max_files=5,
        max_tokens=100_000,
        response_tokens=8_192,
        summarization="minimal",
        retrieval_first=False,
    )

    ctx = WorkerContext(
        system_prompt="Short system prompt",
        recent_messages=[
            {"role": "user", "content": "Small message"},
            {"role": "assistant", "content": "Small response"},
        ],
    )

    messages, metadata = ctx.to_messages(policy=policy)

    assert metadata["truncated"] is False
    assert metadata["dropped_messages"] == 0
    assert len(messages) == 3  # system + 2 messages


# ── BUG-01: Message persistence ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_service_persists_user_and_assistant_messages(monkeypatch):
    """BUG-01: chat_service.chat_stream() must persist both user and assistant messages."""
    from backend.services.chat_service import ChatService

    # Create in-memory SQLite engine with messages table
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        from storage.models import Base
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as db:
        # Create a conversation
        from storage.models import Conversation
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        conv = Conversation(id="test-conv-1", title="Test", created_at=now, updated_at=now)
        db.add(conv)
        await db.commit()

        # Mock _get_provider_config to return None (no provider => fallback)
        async def _mock_config(*args, **kwargs):
            return None

        monkeypatch.setattr(ChatService, "_get_provider_config", _mock_config)

        # Call chat_stream (no provider → fallback message)
        messages_list = [{"role": "user", "content": "Hello world"}]
        chunks = []
        async for chunk in ChatService.chat_stream(
            db, "test-conv-1", messages_list, None, None,
        ):
            chunks.append(chunk)

        # Verify messages were persisted
        from sqlalchemy.future import select
        result = await db.execute(select(Message).where(Message.conversation_id == "test-conv-1").order_by(Message.created_at))
        saved = result.scalars().all()

        assert len(saved) >= 2, f"Expected at least 2 messages (user + assistant), got {len(saved)}"
        assert saved[0].role == "user"
        assert saved[0].content == "Hello world"
        assert saved[0].created_at is not None
        assert saved[1].role == "assistant"
        assert saved[1].created_at is not None

    await engine.dispose()
