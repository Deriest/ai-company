"""Tests for Durable Selective Memory Engine.

Verifies:
- Saving project memory entries
- Project scope isolation (Project A memory does not leak to Project B)
- Superseding outdated memory entries
- Retrieval filtering
"""
import pytest
from storage.models import Base

from backend.memory_engine import (
    save_memory_entry, retrieve_project_memories, supersede_memory_entry
)


@pytest.mark.asyncio
async def test_memory_save_and_retrieve(db_session):
    async with db_session() as session:
        proj_a = "project-alpha-123"
        await save_memory_entry(session, key="database_choice", value="PostgreSQL", project_id=proj_a)

        memories = await retrieve_project_memories(session, project_id=proj_a)
        assert len(memories) == 1
        assert memories[0]["key"] == "database_choice"
        assert memories[0]["value"] == "PostgreSQL"


@pytest.mark.asyncio
async def test_memory_project_scope_isolation(db_session):
    async with db_session() as session:
        proj_a = "project-alpha-123"
        proj_b = "project-beta-456"

        await save_memory_entry(session, key="auth_provider", value="OAuth2 Google", project_id=proj_a)
        await save_memory_entry(session, key="auth_provider", value="JWT Internal", project_id=proj_b)

        mem_a = await retrieve_project_memories(session, project_id=proj_a)
        mem_b = await retrieve_project_memories(session, project_id=proj_b)

        assert len(mem_a) == 1
        assert mem_a[0]["value"] == "OAuth2 Google"

        assert len(mem_b) == 1
        assert mem_b[0]["value"] == "JWT Internal"


@pytest.mark.asyncio
async def test_supersede_memory_entry(db_session):
    async with db_session() as session:
        proj_a = "project-alpha-123"
        entry1 = await save_memory_entry(session, key="style_guide", value="Tailwind v3", project_id=proj_a)

        # Supersede with Tailwind v4
        entry2 = await supersede_memory_entry(session, str(entry1.id), "Tailwind v4")
        assert entry2 is not None

        memories = await retrieve_project_memories(session, project_id=proj_a)
        assert len(memories) == 1
        assert memories[0]["value"] == "Tailwind v4"
