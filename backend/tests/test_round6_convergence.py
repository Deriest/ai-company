"""Round-6 convergence audit fixes — functional verification tests.

Covers:
- Item 1: POST /providers rejects duplicate names with 409 (no duplicate rows).
- Item 2: deleting a project purges its FTS5 rows so /conversations/search
  no longer returns snippets from deleted project content.
- Item 3: agent concurrency cap emits a "queued" status and never hangs —
  normal path (semaphore free) is unaffected, and a full queue degrades to a
  clean error.
- Item 4: the full migration list applies cleanly on a fresh DB, and
  migration 017 recovers if a previous run died mid-rebuild.
"""
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield


# ── Item 1: Provider duplicate-name 409 ─────────────────────────────────

@pytest.mark.asyncio
async def test_provider_duplicate_name_returns_409():
    """POST /providers with an existing name returns 409 instead of creating a
    duplicate row (consistent with POST /providers/config name upsert)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/providers", json={
            "name": "Dup Provider",
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
        })
        assert create.status_code == 200

        dup = await ac.post("/providers", json={
            "name": "Dup Provider",
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
        })
        assert dup.status_code == 409
        assert "already exists" in dup.json()["detail"]

        # Exactly one row for that name.
        from sqlalchemy.future import select
        from backend.models.schema import Provider
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Provider).where(Provider.name == "Dup Provider"))
            assert len(res.scalars().all()) == 1


# ── Item 2: Deleted project content is no longer searchable ─────────────

@pytest.mark.asyncio
async def test_deleted_project_content_not_searchable():
    """Deleting a project removes its FTS5 rows so /conversations/search stops
    returning snippets from the deleted project's conversations."""
    probe = "round6ftsprobe"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        p_res = await ac.post("/projects", json={"name": "Round6 FTS Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["id"]

        c_res = await ac.post("/conversations", json={
            "title": "Round6 FTS Conv",
            "project_id": project_id,
        })
        assert c_res.status_code == 200
        conv_id = c_res.json()["id"]

        m_res = await ac.post(f"/conversations/{conv_id}/messages", json={
            "role": "user",
            "content": f"Electroencephalogram {probe} analysis",
        })
        assert m_res.status_code == 200

        # Searchable before deletion.
        s_res = await ac.get(f"/conversations/search?q={probe}")
        assert s_res.status_code == 200
        assert any(item["conversation_id"] == conv_id for item in s_res.json()), (
            "probe content should be searchable before the project is deleted"
        )

        d_res = await ac.delete(f"/projects/{project_id}")
        assert d_res.status_code == 204

        # Not searchable after deletion.
        s2 = await ac.get(f"/conversations/search?q={probe}")
        assert s2.status_code == 200
        assert not any(item["conversation_id"] == conv_id for item in s2.json()), (
            "probe content must not remain searchable after the project is deleted"
        )


# ── Item 3: Agent concurrency cap never silently hangs ───────────────────

@pytest.mark.asyncio
async def test_agent_run_normal_path_emits_queued_and_releases(monkeypatch):
    """With the semaphore free, /agent/run emits a queued status, runs, and
    returns the semaphore to full capacity (normal path unaffected)."""
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE, AgentRunner

    async def _fake_run_agent(self, *args, **kwargs):
        yield {"type": "content", "content": "Round6 normal path"}
        yield {"type": "done", "iterations": 1, "deliverables": []}

    monkeypatch.setattr(AgentRunner, "run_agent", _fake_run_agent)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with ac.stream(
            "POST", "/agent/run",
            json={"prompt": "hello", "worker_type": "backend"},
        ) as resp:
            body = await resp.aread()

    assert resp.status_code == 200
    events = [
        json.loads(line[6:])
        for line in body.decode().splitlines()
        if line.startswith("data: ")
    ]
    types = [e["type"] for e in events]
    assert "content" in types  # the run actually executed
    queued = [e for e in events if e["type"] == "status" and e.get("status") == "queued"]
    assert queued, "expected a 'queued' status event before execution"
    assert AGENT_RUN_SEMAPHORE._value == 4, "semaphore must be released back to full capacity"


@pytest.mark.asyncio
async def test_agent_run_full_queue_emits_clean_error(monkeypatch):
    """When the concurrency cap is exhausted, /agent/run emits a friendly error
    after the queue timeout instead of silently hanging."""
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE

    # Bound the wait to a tiny value for the test. agent.py resolves the
    # constant via a function-local import at call time, so patching the
    # agent_runner module attribute is sufficient.
    monkeypatch.setattr("backend.services.agent_runner.AGENT_RUN_QUEUE_TIMEOUT", 0.1)

    # Exhaust the 4-slot semaphore.
    for _ in range(4):
        await AGENT_RUN_SEMAPHORE.acquire()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            async with ac.stream(
                "POST", "/agent/run",
                json={"prompt": "hello", "worker_type": "backend"},
            ) as resp:
                body = await resp.aread()

        assert resp.status_code == 200
        events = [
            json.loads(line[6:])
            for line in body.decode().splitlines()
            if line.startswith("data: ")
        ]
        queued = [e for e in events if e["type"] == "status" and e.get("status") == "queued"]
        assert queued, "expected a 'queued' status before the queue timeout"
        errors = [e for e in events if e["type"] == "error"]
        assert errors, "expected a clean error instead of a hang"
        assert "queue is full" in errors[-1]["error"]
    finally:
        for _ in range(4):
            AGENT_RUN_SEMAPHORE.release()


# ── Item 4: Migration crash-safety ───────────────────────────────────────

def _create_backend_schema(sync_conn):
    """Create every table the migration list touches (mirrors init_db)."""
    import storage.models  # noqa: F401
    from storage.models import Base as StorageBase
    import backend.models.schema  # noqa: F401
    import backend.models.conversation  # noqa: F401
    import backend.models.ai_runtime  # noqa: F401
    import backend.models.orchestration  # noqa: F401
    import backend.models.jobs  # noqa: F401
    import backend.models.mcp  # noqa: F401
    import backend.models.local_profile  # noqa: F401
    from backend.database.session import Base as BackendBase

    StorageBase.metadata.create_all(sync_conn)
    BackendBase.metadata.create_all(sync_conn)


@pytest.mark.asyncio
async def test_all_migrations_apply_cleanly_on_fresh_db(monkeypatch):
    """The full migration list (001-018) applies cleanly on a fresh database."""
    import backend.migrations.runner as migration_runner
    from backend.database.session import engine as backend_engine

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(_create_backend_schema)

        monkeypatch.setattr(migration_runner, "engine", test_engine)
        await migration_runner.run_migrations()

        async with test_engine.connect() as conn:
            applied = (
                await conn.execute(text("SELECT version FROM schema_migrations"))
            ).scalars().all()
        expected = {m["version"] for m in migration_runner.MIGRATIONS}
        assert set(applied) == expected, f"applied={sorted(applied)} expected={sorted(expected)}"
    finally:
        monkeypatch.setattr(migration_runner, "engine", backend_engine)
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_fk_off_migration_restores_pragma_on_failure(monkeypatch):
    """Round-6 item 4b: even when a fk_off migration fails, the pooled
    connection must not be left with PRAGMA foreign_keys=OFF."""
    import backend.migrations.runner as migration_runner
    from backend.database.session import engine as backend_engine

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with test_engine.begin() as conn:
            await conn.execute(text("CREATE TABLE discovery_sessions (id VARCHAR PRIMARY KEY)"))
            await conn.execute(text(
                "CREATE TABLE schema_migrations (version VARCHAR PRIMARY KEY, name VARCHAR)"
            ))

        bad_migration = {
            "version": "999",
            "name": "fk_off_failure_test",
            "fk_off": True,
            "up": (
                "CREATE TABLE discovery_sessions_new (id VARCHAR PRIMARY KEY);"
                "THIS IS NOT SQL;"
            ),
        }
        monkeypatch.setattr(migration_runner, "engine", test_engine)
        with pytest.raises(Exception):
            await migration_runner._apply_migration_fk_off(bad_migration)

        # StaticPool reuses the same connection — FK must be back ON.
        async with test_engine.connect() as conn:
            fk = (await conn.execute(text("PRAGMA foreign_keys"))).fetchone()[0]
        assert fk == 1, "PRAGMA foreign_keys must be re-enabled after a failed migration"
    finally:
        monkeypatch.setattr(migration_runner, "engine", backend_engine)
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_migration_017_rebuild_resumes_after_crash(monkeypatch):
    """Migration 017 must recover if a previous run died between DROP TABLE and
    ALTER RENAME (old table missing, _new table already present with data)."""
    import backend.migrations.runner as migration_runner
    from backend.database.session import engine as backend_engine

    migration_017 = next(
        (m for m in migration_runner.MIGRATIONS if m["version"] == "017"), None
    )
    assert migration_017 is not None, "migration 017 not found"

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with test_engine.begin() as conn:
            # Simulated crashed state: discovery_sessions already dropped,
            # discovery_sessions_new exists with data, rename never happened.
            await conn.execute(text("""
                CREATE TABLE discovery_sessions_new (
                    id VARCHAR PRIMARY KEY,
                    conversation_id VARCHAR NOT NULL,
                    user_id VARCHAR,
                    status VARCHAR NOT NULL DEFAULT 'new_request',
                    round_number INTEGER DEFAULT 0,
                    questions_asked INTEGER DEFAULT 0,
                    questions_answered INTEGER DEFAULT 0,
                    context TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await conn.execute(text(
                "INSERT INTO discovery_sessions_new (id, conversation_id, status) "
                "VALUES ('s1', 'c1', 'done')"
            ))
            # Mark every other migration applied so only 017 runs.
            await conn.execute(text(
                "CREATE TABLE schema_migrations (version VARCHAR PRIMARY KEY, "
                "name VARCHAR NOT NULL, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            ))
            for m in migration_runner.MIGRATIONS:
                if m["version"] != "017":
                    await conn.execute(
                        text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
                        {"v": m["version"], "n": m["name"]},
                    )

        monkeypatch.setattr(migration_runner, "engine", test_engine)
        monkeypatch.setattr(migration_runner, "MIGRATIONS", [migration_017])
        await migration_runner.run_migrations()

        async with test_engine.connect() as conn:
            applied = (
                await conn.execute(text("SELECT version FROM schema_migrations"))
            ).scalars().all()
            rows = (
                await conn.execute(
                    text("SELECT id, conversation_id, status FROM discovery_sessions")
                )
            ).all()
        assert "017" in applied, "migration 017 must be marked applied after recovery"
        assert len(rows) == 1, "data must be preserved across the rebuild"
        assert rows[0].id == "s1"
        assert rows[0].status == "done"
    finally:
        monkeypatch.setattr(migration_runner, "engine", backend_engine)
        await test_engine.dispose()