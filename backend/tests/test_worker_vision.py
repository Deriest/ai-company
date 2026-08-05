"""Worker VISION tier tests.

Verifies the worker-pipeline vision path:
(a) ``tier_map`` in ``_llm_with_tools`` / ``_llm_or_fallback`` resolves
    "vision" → ``ModelTier.VISION`` (enum reaches provider_manager.chat);
(b) a worker invoked with model_tier "vision" + an ``image_data_url`` /
    ``image_url`` in context builds an OpenAI multimodal message containing an
    ``image_url`` part;
(c) ``runtime.executor`` passes ``task.context["model_tier"]`` through to the
    worker's task_ctx so a task can be launched with vision.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm.provider import ModelTier, provider_manager


def _fake_worker(agent_id: str = "test_vision_worker"):
    worker = MagicMock()
    worker.agent_id = agent_id
    worker.worker_type = agent_id
    worker.name = f"{agent_id}-worker"
    worker.SYSTEM_PROMPT = "You are a test worker."
    return worker


class _FakeToolExecutor:
    file_diffs = []

    def to_openai_schema(self):
        return []


def _patch_llm():
    """Patch provider_manager so the worker LLM helpers hit a fake provider and
    capture the exact tier + messages they forward to provider_manager.chat."""
    provider = MagicMock()
    provider.config = MagicMock()
    provider.config.name = "fake-provider"
    captured = {}

    async def chat_side_effect(**kwargs):
        captured["tier"] = kwargs.get("tier")
        captured["messages"] = kwargs.get("messages")
        return {
            "content": "Vision analysis complete.",
            "model": "vision-model",
            "raw": {"choices": [{"message": {"content": "Vision analysis complete."}}]},
            "usage": {},
        }

    p1 = patch.object(provider_manager, "get_active_with_key", return_value=provider)
    p2 = patch.object(
        provider_manager, "chat", AsyncMock(side_effect=chat_side_effect)
    )
    return p1, p2, captured


# ── (a) tier_map resolves "vision" → ModelTier.VISION ──────────────

@pytest.mark.asyncio
async def test_llm_with_tools_resolves_vision_tier():
    from workers.base import _llm_with_tools

    p1, p2, captured = _patch_llm()
    with p1, p2:
        result, meta, tool_calls = await _llm_with_tools(
            _fake_worker(),
            "Analyze this image",
            ModelTier.CRAFTER,  # registry default — must be overridden to vision
            0.3,
            "vision_test",
            "fallback-text",
            tool_executor=_FakeToolExecutor(),
            task_context={"model_tier": "vision"},
        )

    assert captured["tier"] is ModelTier.VISION, f"got {captured['tier']!r}"
    assert meta.get("used_fallback") is False


@pytest.mark.asyncio
async def test_llm_or_fallback_resolves_vision_tier():
    from workers.base import _llm_or_fallback

    p1, p2, captured = _patch_llm()
    with p1, p2:
        content, meta = await _llm_or_fallback(
            _fake_worker(),
            "Analyze this image",
            ModelTier.CRAFTER,
            0.3,
            "vision_test",
            "fallback-text",
            task_context={"model_tier": "vision"},
        )

    assert captured["tier"] is ModelTier.VISION, f"got {captured['tier']!r}"
    assert meta.get("used_fallback") is False


# ── (b) image content builds a multimodal message ──────────────────

@pytest.mark.asyncio
async def test_llm_with_tools_builds_image_url_part():
    from workers.base import _llm_with_tools

    data_url = "data:image/png;base64,iVBORw0KGgo="
    p1, p2, captured = _patch_llm()
    with p1, p2:
        await _llm_with_tools(
            _fake_worker(),
            "What is in this image?",
            ModelTier.CRAFTER,
            0.3,
            "vision_test",
            "fallback-text",
            tool_executor=_FakeToolExecutor(),
            task_context={"model_tier": "vision", "image_data_url": data_url},
        )

    user_content = captured["messages"][1]["content"]
    assert isinstance(user_content, list), "user message must be multimodal parts"
    assert user_content[0] == {"type": "text", "text": "What is in this image?"}
    assert user_content[1] == {
        "type": "image_url",
        "image_url": {"url": data_url},
    }


@pytest.mark.asyncio
async def test_llm_or_fallback_accepts_image_url():
    from workers.base import _llm_or_fallback

    p1, p2, captured = _patch_llm()
    with p1, p2:
        await _llm_or_fallback(
            _fake_worker(),
            "Describe this image",
            ModelTier.CRAFTER,
            0.3,
            "vision_test",
            "fallback-text",
            task_context={"model_tier": "vision", "image_url": "https://example.com/img.png"},
        )

    user_content = captured["messages"][1]["content"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"] == "https://example.com/img.png"


@pytest.mark.asyncio
async def test_no_image_no_image_part():
    """Without image data the user message stays a plain string (default path)."""
    from workers.base import _llm_with_tools

    p1, p2, captured = _patch_llm()
    with p1, p2:
        await _llm_with_tools(
            _fake_worker(),
            "Just answer this",
            ModelTier.CRAFTER,
            0.3,
            "vision_test",
            "fallback-text",
            tool_executor=_FakeToolExecutor(),
            task_context={"model_tier": "vision"},
        )

    user_content = captured["messages"][1]["content"]
    assert isinstance(user_content, str)


# ── registry passthrough + default behavior ────────────────────────

def test_model_policy_accepts_vision_and_flows_through_registry():
    """A ModelPolicy(tier="vision") flows verbatim through get_model_config and
    is mapped to ModelTier.VISION by the worker tier_map."""
    from agents.context_assembly import get_model_config
    from agents.registry import (
        AgentDefinition, AgentIdentity, AgentSoul, HeartbeatPolicy,
        ModelPolicy, ToolPermissions, _register, AGENT_REGISTRY,
    )

    agent = AgentDefinition(
        identity=AgentIdentity(
            id="vision_agent_tmp", name="Vizzy", role="Vision Tester",
            tier="crafter", department="Engineering", phase="Implementation",
            description="", personality="",
        ),
        soul=AgentSoul(
            core_purpose="test", engineering_philosophy="test", quality_bar="test",
            risk_philosophy="test", evidence_standards="test",
            collaboration_style="test", escalation_policy="test",
            anti_patterns="test", system_prompt="You are a vision test worker.",
        ),
        tools=ToolPermissions(allowed=[]),
        model=ModelPolicy(tier="vision", temperature=0.2, timeout=60),
        heartbeat=HeartbeatPolicy(),
    )
    _register(agent)
    try:
        cfg = get_model_config("vision_agent_tmp")
        assert cfg["tier"] == "vision", "get_model_config must flow tier verbatim"
    finally:
        AGENT_REGISTRY.pop("vision_agent_tmp", None)


@pytest.mark.asyncio
async def test_default_tier_kept_when_no_override():
    """Without model_tier in context the worker keeps its default registry tier."""
    from workers.base import _llm_with_tools

    p1, p2, captured = _patch_llm()
    with p1, p2:
        await _llm_with_tools(
            _fake_worker(),  # unknown agent → get_model_config returns crafter
            "Do the thing",
            ModelTier.THINKER,
            0.3,
            "default_test",
            "fallback-text",
            tool_executor=_FakeToolExecutor(),
            task_context={},
        )

    assert captured["tier"] is ModelTier.CRAFTER, f"got {captured['tier']!r}"


# ── (c) executor passes model_tier through to the worker ───────────

@pytest.mark.asyncio
async def test_executor_passes_model_tier_into_task_ctx(db_session):
    """runtime.executor reads task.context['model_tier'] and forwards it to the
    worker's task_ctx."""
    from runtime.executor import execute_task
    from storage.models import Project, Task, TaskStatus, TaskType
    from workers.base import WORKER_REGISTRY, WorkerResult

    captured = {}

    class _FakeBackendWorker:
        agent_id = "backend"
        worker_type = "backend"
        name = "backend-worker"
        SYSTEM_PROMPT = "You are a test backend worker."

        async def run_with_timeout(self, task_ctx, timeout=120):
            captured["model_tier"] = task_ctx.get("model_tier")
            return WorkerResult(success=True, output="```python app.py\nprint('hi')\n```")

    original = WORKER_REGISTRY["backend"]
    WORKER_REGISTRY["backend"] = _FakeBackendWorker
    try:
        async with db_session() as session:
            proj = await session.get(Project, "proj-1")
            assert proj is not None, "db_session fixture seeds proj-1"
            task = Task(
                id="vision-task-exec-1",
                project_id="proj-1",
                title="Analyze image",
                description="Analyze the uploaded image",
                type=TaskType.FEATURE.value,
                status=TaskStatus.CREATED.value,
                worker_type="backend",
                approval_required=False,
                progress=0,
                context={
                    "model_tier": "vision",
                    "triage": {
                        "level": "QUICK",
                        "scope": "localized",
                        "risk": "low",
                        "confidence": 0.9,
                        "reason": "test",
                        "guardrails_triggered": [],
                        "selected_workers": ["backend"],
                        "required_verification": [],
                        "skip_phases": {
                            "discovery": "skip",
                            "investigate": "skip",
                            "planning": "skip",
                            "verification": "skip",
                            "closeout": "skip",
                        },
                    },
                    "execution_level": "QUICK",
                    "phase_semantics": {},
                },
            )
            session.add(task)
            await session.commit()
            result = await execute_task(session, task)
            assert isinstance(result, dict) and "success" in result
    finally:
        WORKER_REGISTRY["backend"] = original

    assert captured.get("model_tier") == "vision", "model_tier must reach the worker"