"""Regression coverage for defects found in the v2.4.6 full-explore QA."""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import backend.migrations.runner as migration_runner
from backend.database.session import engine as backend_engine
from backend.services.tool_chat_service import ToolAwareChatService
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
        monkeypatch.setattr(migration_runner, "MIGRATIONS", [migration_runner.MIGRATIONS[-1]])
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
