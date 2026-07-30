"""Tests for First-Class Skill Engine.

Verifies:
- Skill seeding & listing
- Enabling & disabling skills
- Worker skill assignments
- Worker-specific skill resolution (Worker A receives skill X, Worker B does not)
"""
import pytest
import storage.database
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from storage.models import Base

from backend.skill_engine import (
    seed_builtin_skills, list_skills, toggle_skill, assign_skill_workers, resolve_skills_for_worker
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_skill_seeding_and_listing(db_session):
    async with db_session() as session:
        await seed_builtin_skills(session)
        skills = await list_skills(session)
        assert len(skills) >= 6
        skill_ids = [s["skill_id"] for s in skills]
        assert "api-completeness-audit" in skill_ids
        assert "security-audit" in skill_ids


@pytest.mark.asyncio
async def test_worker_skill_resolution_isolation(db_session):
    async with db_session() as session:
        await seed_builtin_skills(session)

        # Worker A (security) should receive security-audit
        sec_skills = await resolve_skills_for_worker(session, "security")
        sec_text = " ".join(sec_skills)
        assert "security-audit" in sec_text

        # Worker B (designer) should NOT receive security-audit
        des_skills = await resolve_skills_for_worker(session, "designer")
        des_text = " ".join(des_skills)
        assert "security-audit" not in des_text


@pytest.mark.asyncio
async def test_toggle_skill_disables_injection(db_session):
    async with db_session() as session:
        await seed_builtin_skills(session)

        # Disable systematic-debugging
        ok = await toggle_skill(session, "systematic-debugging", False)
        assert ok is True

        dbg_skills = await resolve_skills_for_worker(session, "debugger")
        dbg_text = " ".join(dbg_skills)
        assert "systematic-debugging" not in dbg_text

        # Re-enable
        await toggle_skill(session, "systematic-debugging", True)
        dbg_skills_enabled = await resolve_skills_for_worker(session, "debugger")
        assert "systematic-debugging" in " ".join(dbg_skills_enabled)
