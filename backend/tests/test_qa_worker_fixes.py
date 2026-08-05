"""QA Task Tests for worker/provider/policy fixes.

Tests cover:
- H2: LLM provider routing uses keyed provider even when active has no key
- M1: tool permissions layer properly enforces read-only/coder roles
- M2: policy engine allows workers on task:<id> URIs
- M5: QA worker verifies workspace via workspace_manager (settings.WORKSPACE_DIR)
"""
import pytest
import os
from pathlib import Path


# ── Test H2: Provider routing through keyed provider ────────────────────


@pytest.mark.asyncio
async def test_h2_provider_manager_get_active_with_key():
    """H2: register empty-key provider first, keyed provider second; keyed provider wins.

    When an env-configured router is registered first (empty api_key) and a DB
    provider is registered second (with an actual API key), get_active() returns
    the empty-key provider (first registered), but get_active_with_key() returns
    the keyed provider. ProviderManager.chat() must route through the latter.
    """
    from llm.provider import ProviderManager, ProviderConfig

    config_empty = ProviderConfig(name="env_router", base_url="http://router/v1", api_key="")
    config_keyed = ProviderConfig(name="db_openai", base_url="http://openai/v1", api_key="sk-actualkey")

    pm = ProviderManager()
    pm.register(config_empty)  # empty-key provider registered first, becomes active
    pm.register(config_keyed)  # keyed provider registered second

    assert pm._active == "env_router"  # active is still the first registered
    assert pm.get_active().config.name == "env_router"

    # get_active_with_key() must prefer the provider with a usable key
    keyed = pm.get_active_with_key()
    assert keyed is not None, "Should find a provider with usable key"
    assert keyed.config.name == "db_openai", "Should return the keyed provider, not the empty-key active"


@pytest.mark.asyncio
async def test_h2_chat_routes_to_keyed_provider():
    """H2: ProviderManager.chat() must use the keyed provider, not empty-key active."""
    from llm.provider import ProviderManager, ProviderConfig, LLMError

    config_empty = ProviderConfig(name="env_router", base_url="http://router/v1", api_key="")
    config_keyed = ProviderConfig(name="db_openai", base_url="http://openai/v1", api_key="sk-actualkey")

    pm = ProviderManager()
    pm.register(config_empty)
    pm.register(config_keyed)

    calls = []

    async def fake_chat(messages, tier=None, **kwargs):
        # Record which provider handled the call
        calls.append("called")
        return {"content": "response from keyed provider"}

    # Patch the keyed provider's chat method so we can verify routing
    keyed_provider = pm.get_provider("db_openai")
    keyed_provider.chat = fake_chat

    # Also make empty provider fail loudly if it gets called (would mean routing is broken)
    async def failing_chat(messages, tier=None, **kwargs):
        raise AssertionError("Empty-key provider should NOT handle the chat request")

    empty_provider = pm.get_provider("env_router")
    empty_provider.chat = failing_chat

    result = await pm.chat([{"role": "user", "content": "hi"}], tier="crafter")
    assert result["content"] == "response from keyed provider"
    assert len(calls) == 1, "Exactly one provider should have been called"


# ── Test M1: Tool permissions enforce correct roles ──────────────────────


class TestToolPermissionsM1:
    """Tests for M1: tool permission layer correctness."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test to ensure fresh load."""
        from backend.services.tool_permissions import clear_cache
        clear_cache()
        yield

    def test_rex_denies_shell_and_write(self):
        """Read-only role rex denies write_file/shell per M1 spec."""
        from backend.services.tool_permissions import check_tool_permission
        assert check_tool_permission("rex", "shell") is False
        assert check_tool_permission("rex", "write_file") is False
        assert check_tool_permission("rex", "read_file") is True
        assert check_tool_permission("rex", "explore") is True

    def test_review_denies_shell_and_write(self):
        """Read-only role review denies write_file/shell per M1 spec."""
        from backend.services.tool_permissions import check_tool_permission
        assert check_tool_permission("review", "shell") is False
        assert check_tool_permission("review", "write_file") is False
        assert check_tool_permission("review", "read_file") is True

    def test_security_denies_shell_and_write(self):
        """Security role explicitly made read-only per M1 spec."""
        from backend.services.tool_permissions import check_tool_permission
        assert check_tool_permission("security", "shell") is False
        assert check_tool_permission("security", "write_file") is False
        assert check_tool_permission("security", "read_file") is True

    def test_backend_allows_shell_and_write(self):
        """Coder role backend allows write_file/shell per M1 spec."""
        from backend.services.tool_permissions import check_tool_permission
        assert check_tool_permission("backend", "shell") is True
        assert check_tool_permission("backend", "write_file") is True
        assert check_tool_permission("backend", "read_file") is True

    def test_coding_alias_allows_shell_and_write(self):
        """Coding worker alias (not in AGENT_REGISTRY) defaults to coder permissions."""
        from backend.services.tool_permissions import check_tool_permission
        assert check_tool_permission("coding", "shell") is True
        assert check_tool_permission("coding", "write_file") is True
        assert check_tool_permission("coding", "read_file") is True


# ── Test M2: Policy engine allows workers on task URIs ───────────────────


class TestPolicyM2TaskURIs:
    """Tests for M2: policy engine correctly handles task:<id> resources."""

    def test_coding_worker_allowed_on_task_uri(self):
        """Coding worker should be ALLOW on task:<id> URI (M2 requirement)."""
        from policy.engine import policy, Decision
        result = policy.evaluate(action="worker.execute", worker_type="coding", resource="task:t123")
        assert result.decision == Decision.ALLOW, f"Expected ALLOW for coding on task URI, got {result.reason}"

    def test_deployment_worker_allowed_on_task_uri(self):
        """Deployment worker should be ALLOW on task:<id> URI (M2 requirement)."""
        from policy.engine import policy, Decision
        result = policy.evaluate(action="worker.execute", worker_type="deployment", resource="task:t123")
        assert result.decision == Decision.ALLOW, f"Expected ALLOW for deployment on task URI, got {result.reason}"

    def test_testing_worker_allowed_on_task_uri(self):
        """Testing worker should be ALLOW on task:<id> URI (M2 requirement)."""
        from policy.engine import policy, Decision
        result = policy.evaluate(action="worker.execute", worker_type="testing", resource="task:t123")
        assert result.decision == Decision.ALLOW, f"Expected ALLOW for testing on task URI, got {result.reason}"

    def test_file_scope_check_skipped_for_task_uri(self):
        """File-scope restriction must not apply to task: URIs (M2 core fix)."""
        from policy.engine import policy, Decision
        # A "task:" resource doesn't match any FILE_SCOPE pattern, but the fix
        # ensures the file-scope component is skipped entirely for task URIs.
        result = policy.evaluate(action="worker.execute", worker_type="coding", resource="task:t999")
        assert result.decision == Decision.ALLOW, "Task URIs should bypass file-scope component"


# ── Test M5: QA worker workspace resolution ─────────────────────────────


class TestQAWorkspaceM5:
    """Tests for M5: QA worker resolves workspace through workspace_manager."""

    @pytest.mark.asyncio
    async def test_requirements_md_in_settings_workspace_found_by_qa(self, tmp_path, monkeypatch):
        """M5 test: REQUIREMENTS.md placed under settings.WORKSPACE_DIR/<task_id> is discovered by QA."""
        # Set AIC_DATA_DIR so workspace_manager._workspace_base() uses our tmp_path
        monkeypatch.setenv("AIC_DATA_DIR", str(tmp_path))

        from workers.base import TestingWorker

        task_id = "test-task-m5"
        workspace_dir = tmp_path / "workspace" / task_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Place REQUIREMENTS.md in the workspace (the real deliverables location)
        req_content = "# Requirements\nThis is the project."
        req_path = workspace_dir / "REQUIREMENTS.md"
        req_path.write_text(req_content)

        # Run QA verification with task_context pointing to this workspace
        # Use an isolated empty repo_path so QA doesn't try to run pytest/npm
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(exist_ok=True)
        qa_worker = TestingWorker()
        ctx = {
            "task_id": task_id,
            "title": "Test Task",
            "description": "QA verification test",
            "repo_path": str(repo_dir),
        }

        result = await qa_worker.execute(ctx)

        # QA should report SUCCESS because REQUIREMENTS.md exists
        assert result.success is True, f"QA should pass when REQUIREMENTS.md is present. Output: {result.output[:500]}"
        assert "REQUIREMENTS.md: PRESENT" in result.output

    @pytest.mark.asyncio
    async def test_empty_workspace_falls_to_repo_test_framework(self, tmp_path, monkeypatch):
        """Empty workspace should fall back to repo_path-based testing (if applicable)."""
        monkeypatch.setenv("AIC_DATA_DIR", str(tmp_path))

        from workers.base import TestingWorker

        task_id = "empty-task"
        workspace_dir = tmp_path / "workspace" / task_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        # Don't create any files - leave it empty

        qa_worker = TestingWorker()
        # Use an isolated empty repo_path so QA doesn't try to run pytest/npm
        repo_dir = tmp_path / "repo_empty"
        repo_dir.mkdir(exist_ok=True)
        ctx = {
            "task_id": task_id,
            "title": "Empty Task",
            "description": "",
            "repo_path": str(repo_dir),
        }

        result = await qa_worker.execute(ctx)
        # With empty workspace and no test framework at repo_path ("."), should report SKIPPED
        assert "**skipped**" in result.output.lower(), f"Empty workspace should SKIPPED, got: {result.output[:300]}"
