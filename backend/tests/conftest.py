"""Test isolation for the backend suite.

QA-HARDENING: tests previously shared the persistent backend/data/aic.db,
which caused DB-state flakiness (StaleDataError / count mismatches) when a
live backend or a prior test run left rows behind. This conftest redirects
AIC_DATA_DIR to a per-session temp directory BEFORE backend.config is first
imported, so every test run uses a clean, isolated SQLite database.

F19: the in-memory ``db_session`` fixture (previously duplicated in
test_e2e.py / test_memory_engine.py / test_skills_engine.py) is consolidated
here so all three suites share a single definition.
"""
import os
import secrets
import tempfile

# Must be set before backend.config / backend.database.session are imported.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="aic-test-data-")
os.environ["AIC_DATA_DIR"] = _TEST_DATA_DIR
# GAP-1 FIX: JWT secret must be provided via environment variable (no file
# fallback). Tests generate a fresh secret per session so the suite runs
# hermetically without touching any real secret. MUST be set before
# backend.config is imported.
os.environ.setdefault("AIC_JWT_SECRET", secrets.token_hex(32))
# Enable the deterministic test flag so the auth fail-open (and the
# localhost Host-header allowlist for httpx ASGITransport "test") applies
# during the test run but never at runtime. Read by backend/api/dependencies.py
# and backend/main.py. MUST be set here, before backend.config is imported,
# so the modules observe it consistently.
os.environ["AIC_TESTING"] = "1"
# Force the LLM provider OFF in the test suite. init_provider_from_env() reads
# from backend.config.settings (which loads the repo .env), so without this a
# test creating a task would call the REAL gateway and hang. Pydantic-settings
# gives OS env precedence over .env, so empty values here disable the provider
# while keeping the .env fix intact for production runs.
os.environ["AIC_LLM_BASE_URL"] = ""
os.environ["AIC_LLM_API_KEY"] = ""
os.environ["AIC_LLM_PROVIDER_NAME"] = ""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
import storage.database
from storage.models import Base, User, Project, Conversation, Role


@pytest.fixture
async def db_session():
    """Provide an async session with clean in-memory SQLite.

    Creates the schema, points ``storage.database`` at the in-memory engine
    (so modules that resolve the session internally hit the same DB), and
    seeds the base project/conversation used by the E2E tests. The global
    factory/engine references are restored and the engine disposed on
    teardown.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    old_factory = storage.database.async_session
    old_engine = storage.database.engine
    storage.database.async_session = factory
    storage.database.engine = engine

    async with factory() as session:
        user = User(id="user-1", username="admin", hashed_password="x", role=Role.OWNER.value, is_active=True)
        project = Project(id="proj-1", name="Test", slug="test", description="E2E", owner_id="user-1")
        conv = Conversation(id="conv-1", user_id="user-1", project_id="proj-1", title="Test", context={"project_id": "proj-1"})
        session.add_all([user, project, conv])
        await session.commit()

    yield factory
    storage.database.async_session = old_factory
    storage.database.engine = old_engine
    await engine.dispose()