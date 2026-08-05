"""Vision-capability heuristic + GitHub token (GHP) encryption tests.

Feature 1: vision-capable models must surface in the provider model dropdown.
``infer_capabilities`` must flag o4 / qwen-vl / llava / pixtral / llama-4 /
gpt-4o etc., and the test-ephemeral path must not hardcode vision=False.

Feature 2: the GitHub personal token is persisted encrypted (Fernet) on the
LocalProfile row and masked as "***" on read.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from backend.services.provider_client import infer_capabilities
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal


# ── Feature 1a: vision heuristic ─────────────────────────────────────────

class TestVisionCapabilityHeuristic:
    """infer_capabilities must detect multimodal models and skip plain models."""

    VISION_MODELS = [
        # o4 (OpenAI reasoning-vision)
        "o4",
        "o4-mini",
        "o4-mini-2025-07-24",
        # qwen-vl family
        "qwen2.5-vl",
        "qwen2.5-vl-72b-instruct",
        "qwen-vl-plus",
        "qwen2.5-vlm",
        # llava
        "llava-hf/llava-1.5-7b-hf",
        "llava-v1.6-vicuna-7b",
        # pixtral (Mistral multimodal)
        "pixtral-12b-2409",
        "pixtral-large",
        # llama-4 family (natively multimodal)
        "llama-4-vision",
        "meta-llama/llama-4-maverick",
        "meta-llama/llama-4-scout",
        # gpt-4o / gpt-4.1
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        # gemini + claude families (natively multimodal)
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "claude-sonnet-4.5",
        "claude-3-opus",
        "claude-3-5-sonnet",
        "anthropic/claude-sonnet-4-5",
        # explicit image marker
        "novel-image-generator",
    ]

    NON_VISION_MODELS = [
        # plain code / text models must NOT be flagged vision
        "deepseek-coder",
        "deepseek-chat",
        "qwen3-coder",
        "qwen2.5-coder-32b",
        "llama-3.3-70b-instruct",
        "llama-3.1-8b",
        "codestral-latest",
        "mistral-large",
        "glm-4.5",
        "grok-4",
    ]

    @pytest.mark.parametrize("model_id", VISION_MODELS)
    def test_vision_models_detected(self, model_id):
        caps = infer_capabilities(model_id, {})
        assert caps["supports_vision"] is True, (
            f"{model_id} should be detected as vision-capable"
        )

    @pytest.mark.parametrize("model_id", NON_VISION_MODELS)
    def test_non_vision_models_not_detected(self, model_id):
        caps = infer_capabilities(model_id, {})
        assert caps["supports_vision"] is False, (
            f"{model_id} should NOT be detected as vision-capable"
        )


# ── Feature 1b: test-ephemeral uses real capabilities ────────────────────

class TestTestEphemeralUsesInferredCapabilities:
    """_run_test (POST /providers/test-ephemeral) must not hardcode vision=False."""

    @pytest.mark.asyncio
    async def test_run_test_uses_inferred_vision(self, monkeypatch):
        from backend.api.routes.providers import _run_test

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                self.closed = False

            async def test_connection(self):
                return {"latency_ms": 42, "version": "openai-compatible/v1"}

            async def fetch_models(self):
                # Mirrors ProviderClient.fetch_models() -> (normalized, latency).
                return [
                    {
                        "model_id": "gpt-4o",
                        "display_name": "gpt-4o",
                        "owned_by": "openai",
                        "raw_metadata": {},
                        "context_window": 128000,
                        "context_source": "pattern",
                        "supports_vision": True,
                        "supports_tool_calling": True,
                        "supports_streaming": True,
                        "supports_json_mode": True,
                        "supports_reasoning": False,
                        "supports_function_calling": True,
                        "supports_embeddings": False,
                        "max_output_tokens": 16384,
                    },
                    {
                        "model_id": "deepseek-coder",
                        "display_name": "deepseek-coder",
                        "owned_by": "deepseek",
                        "raw_metadata": {},
                        "context_window": 128000,
                        "context_source": "pattern",
                        "supports_vision": False,
                        "supports_tool_calling": True,
                        "supports_streaming": True,
                        "supports_json_mode": True,
                        "supports_reasoning": False,
                        "supports_function_calling": True,
                        "supports_embeddings": False,
                        "max_output_tokens": 16384,
                    },
                ], 42

            async def close(self):
                self.closed = True

        monkeypatch.setattr(
            "backend.api.routes.providers.ProviderClient", _FakeClient
        )

        res = await _run_test("https://example.test/v1", "fake-key")
        assert res.ok is True
        assert res.models is not None
        by_id = {m.id: m for m in res.models}
        assert by_id["gpt-4o"].capabilities.vision is True
        assert by_id["deepseek-coder"].capabilities.vision is False
        assert by_id["gpt-4o"].capabilities.maxOutputTokens == 16384


# ── Feature 2: GitHub token round-trip ───────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_github_token_round_trip():
    """PATCH /profile saves the token encrypted; GET /profile masks it as ***;
    and the stored value decrypts back to the original."""
    from backend.services.crypto import decrypt
    from backend.services.profile_service import get_profile

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Ensure a profile exists (created on first launch).
        async with AsyncSessionLocal() as db:
            existing = await get_profile(db)
        if existing is None:
            resp = await ac.post("/profile", json={"displayName": "GHP Test"})
            assert resp.status_code == 200
            assert resp.json()["githubToken"] == ""

        # GET before setting the token → empty, not masked.
        get0 = await ac.get("/profile")
        assert get0.status_code == 200
        assert get0.json()["githubToken"] == ""

        # PATCH with a real token → saved encrypted, masked on response.
        patch = await ac.patch("/profile", json={"github_token": "ghp_test_token_123"})
        assert patch.status_code == 200
        assert patch.json()["githubToken"] == "***"

        # GET returns the mask, never the plaintext.
        get1 = await ac.get("/profile")
        assert get1.status_code == 200
        assert get1.json()["githubToken"] == "***"

        # The DB row holds ciphertext (not plaintext) and decrypts back.
        async with AsyncSessionLocal() as db:
            profile = await get_profile(db)
            assert profile.github_token is not None
            assert profile.github_token != "ghp_test_token_123"
            assert decrypt(profile.github_token) == "ghp_test_token_123"

        # Re-sending the mask must NOT overwrite the stored token.
        patch2 = await ac.patch("/profile", json={"github_token": "***"})
        assert patch2.status_code == 200
        async with AsyncSessionLocal() as db:
            profile = await get_profile(db)
            assert decrypt(profile.github_token) == "ghp_test_token_123"

        # An empty string clears the stored token.
        patch3 = await ac.patch("/profile", json={"github_token": ""})
        assert patch3.status_code == 200
        assert patch3.json()["githubToken"] == ""
        async with AsyncSessionLocal() as db:
            profile = await get_profile(db)
            assert profile.github_token in (None, "")


# ── Migration 019 ────────────────────────────────────────────────────────

class TestMigration019:
    def test_migration_019_registered(self):
        """Migration 019 adds github_token to local_profile."""
        from backend.migrations.runner import MIGRATIONS

        migration_019 = next((m for m in MIGRATIONS if m["version"] == "019"), None)
        assert migration_019 is not None
        assert migration_019["name"] == "add_github_token_to_local_profile"
        assert "github_token" in migration_019["up"]

    @pytest.mark.asyncio
    async def test_migration_019_applies_cleanly(self, monkeypatch):
        """Truly apply 019 against a pre-019 local_profile table (no column)."""
        import backend.migrations.runner as migration_runner
        from backend.database.session import engine as backend_engine

        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        try:
            async with test_engine.begin() as conn:
                # Pre-019 schema: local_profile WITHOUT github_token.
                await conn.execute(text("""
                    CREATE TABLE local_profile (
                        id VARCHAR PRIMARY KEY,
                        display_name VARCHAR NOT NULL,
                        device_id VARCHAR UNIQUE NOT NULL,
                        app_version VARCHAR,
                        onboarding_completed BOOLEAN,
                        active_project_id VARCHAR,
                        approval_config VARCHAR,
                        created_at TIMESTAMP,
                        last_seen TIMESTAMP
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                # Mark everything up to 018 as already applied so only 019 runs.
                for m in migration_runner.MIGRATIONS:
                    if m["version"] != "019":
                        await conn.execute(text(
                            "INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"
                        ), {"v": m["version"], "n": m["name"]})

            monkeypatch.setattr(migration_runner, "engine", test_engine)
            await migration_runner.run_migrations()

            async with test_engine.connect() as conn:
                cols = (await conn.execute(text("PRAGMA table_info(local_profile)"))).fetchall()
                col_names = {row[1] for row in cols}
                assert "github_token" in col_names, (
                    "migration 019 must add github_token to local_profile"
                )
                applied = (
                    await conn.execute(text("SELECT version FROM schema_migrations"))
                ).scalars().all()
                assert "019" in set(applied)
        finally:
            monkeypatch.setattr(migration_runner, "engine", backend_engine)
            await test_engine.dispose()