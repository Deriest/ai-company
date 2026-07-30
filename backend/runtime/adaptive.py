"""Capability-driven adaptive runtime policies.

All decisions are derived from provider/model metadata or conservative defaults.
No vendor or model-name branching is permitted in this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ContextClass(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class MemoryMode(str, Enum):
    SESSION_ONLY = "session_only"
    CHECKPOINT = "checkpoint_memory"
    REPOSITORY = "repository_memory"
    SEMANTIC = "semantic_memory"
    VECTOR = "vector_memory"
    HYBRID = "hybrid_memory"


@dataclass(frozen=True)
class ModelCapabilities:
    provider: str
    model: str
    version: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    tool_calling: bool | None = None
    json_mode: bool | None = None
    reasoning: bool | None = None
    streaming: bool | None = None
    vision: bool | None = None
    image_generation: bool | None = None
    embeddings: bool | None = None
    function_calling: bool | None = None
    parallel_requests: bool | None = None
    mcp: bool | None = None
    local: bool | None = None
    source: str = "conservative_default"
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPolicy:
    classification: str
    history_message_limit: int
    prompt_budget_tokens: int
    response_budget_tokens: int
    summarization: str
    retrieval_first: bool
    task_batch_size: int


@dataclass(frozen=True)
class MemoryPolicy:
    mode: str
    retrieval_limit: int
    checkpoint_every_steps: int
    semantic_retrieval: bool
    repository_memory: bool


@dataclass(frozen=True)
class WorkerPolicy:
    planning_depth: str
    max_parallel_workers: int
    prompt_detail: str
    verification_frequency: str
    checkpoint_interval_steps: int
    evidence_level: str
    max_retries: int


@dataclass(frozen=True)
class AdaptiveRuntimeProfile:
    profile_id: str
    provider: str
    model: str
    capabilities: ModelCapabilities
    context: ContextPolicy
    memory: MemoryPolicy
    worker: WorkerPolicy
    checkpoint_strategy: str
    retrieval_strategy: str
    conversation_strategy: str
    execution_strategy: str
    fallback_strategy: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["active_policies"] = {
            "context": self.context.classification,
            "memory": self.memory.mode,
            "worker": self.worker.planning_depth,
            "checkpoint": self.checkpoint_strategy,
            "retrieval": self.retrieval_strategy,
            "conversation": self.conversation_strategy,
            "execution": self.execution_strategy,
            "fallback": self.fallback_strategy,
        }
        return data


_BOOL_ALIASES = {
    "tool_calling": ("tool_calling", "supports_tools", "supports_tool_calling"),
    "json_mode": ("json_mode", "supports_json", "supports_json_mode"),
    "reasoning": ("reasoning", "supports_reasoning", "supports_thinking"),
    "streaming": ("streaming", "supports_streaming"),
    "vision": ("vision", "supports_vision"),
    "image_generation": ("image_generation", "supports_image_generation"),
    "embeddings": ("embeddings", "supports_embeddings"),
    "function_calling": ("function_calling", "supports_function_calling"),
    "parallel_requests": ("parallel_requests", "supports_parallel_requests"),
    "mcp": ("mcp", "supports_mcp"),
    "local": ("local", "is_local"),
}


def _first(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "supported"}:
            return True
        if normalized in {"false", "no", "0", "unsupported"}:
            return False
    return None


def capabilities_from_metadata(
    provider: str,
    model: str,
    metadata: Mapping[str, Any] | None = None,
    *,
    source: str = "provider_metadata",
) -> ModelCapabilities:
    """Normalize provider-neutral metadata into a capability profile.

    Unknown values remain None. The policy engine treats unknown capability as
    unavailable/conservative rather than inferring from a vendor or model name.
    """
    raw = dict(metadata or {})
    nested = raw.get("capabilities")
    if isinstance(nested, Mapping):
        raw = {**raw, **nested}

    bools: dict[str, bool | None] = {}
    for field_name, aliases in _BOOL_ALIASES.items():
        bools[field_name] = _optional_bool(_first(raw, *aliases))

    return ModelCapabilities(
        provider=provider,
        model=model,
        version=_first(raw, "version", "model_version"),
        context_window=_positive_int(
            _first(raw, "context_window", "context_length", "max_context_tokens")
        ),
        max_output_tokens=_positive_int(
            _first(raw, "max_output_tokens", "max_completion_tokens", "output_limit")
        ),
        tool_calling=bools["tool_calling"],
        json_mode=bools["json_mode"],
        reasoning=bools["reasoning"],
        streaming=bools["streaming"],
        vision=bools["vision"],
        image_generation=bools["image_generation"],
        embeddings=bools["embeddings"],
        function_calling=bools["function_calling"],
        parallel_requests=bools["parallel_requests"],
        mcp=bools["mcp"],
        local=bools["local"],
        source=source if raw else "conservative_default",
    )


def generate_runtime_profile(cap: ModelCapabilities) -> AdaptiveRuntimeProfile:
    """Generate all runtime policies from one immutable capability profile."""
    window = cap.context_window or 0
    if window >= 100_000:
        context_class = ContextClass.LARGE
        context = ContextPolicy(
            classification=context_class.value,
            history_message_limit=40,
            prompt_budget_tokens=min(64_000, max(8_000, int(window * 0.55))),
            response_budget_tokens=min(cap.max_output_tokens or 8_192, 8_192),
            summarization="minimal",
            retrieval_first=False,
            task_batch_size=8,
        )
    elif window >= 32_000:
        context_class = ContextClass.MEDIUM
        context = ContextPolicy(
            classification=context_class.value,
            history_message_limit=16,
            prompt_budget_tokens=min(20_000, int(window * 0.55)),
            response_budget_tokens=min(cap.max_output_tokens or 4_096, 4_096),
            summarization="periodic",
            retrieval_first=True,
            task_batch_size=4,
        )
    else:
        context_class = ContextClass.SMALL
        effective = window or 8_192
        context = ContextPolicy(
            classification=context_class.value,
            history_message_limit=6,
            prompt_budget_tokens=max(2_048, int(effective * 0.45)),
            response_budget_tokens=min(cap.max_output_tokens or 2_048, 2_048),
            summarization="aggressive",
            retrieval_first=True,
            task_batch_size=1,
        )

    if cap.embeddings is True and context_class == ContextClass.LARGE:
        memory_mode = MemoryMode.HYBRID
    elif cap.embeddings is True:
        memory_mode = MemoryMode.SEMANTIC
    elif context_class == ContextClass.LARGE:
        memory_mode = MemoryMode.REPOSITORY
    elif context_class == ContextClass.MEDIUM:
        memory_mode = MemoryMode.CHECKPOINT
    else:
        memory_mode = MemoryMode.SESSION_ONLY

    memory = MemoryPolicy(
        mode=memory_mode.value,
        retrieval_limit={ContextClass.SMALL: 3, ContextClass.MEDIUM: 6, ContextClass.LARGE: 10}[context_class],
        checkpoint_every_steps={ContextClass.SMALL: 2, ContextClass.MEDIUM: 5, ContextClass.LARGE: 10}[context_class],
        semantic_retrieval=cap.embeddings is True,
        repository_memory=memory_mode in {MemoryMode.REPOSITORY, MemoryMode.HYBRID},
    )

    parallel_cap = 4 if cap.parallel_requests is True else 1
    if context_class == ContextClass.SMALL:
        parallel_cap = 1
    elif context_class == ContextClass.MEDIUM:
        parallel_cap = min(parallel_cap, 2)

    worker = WorkerPolicy(
        planning_depth={ContextClass.SMALL: "incremental", ContextClass.MEDIUM: "structured", ContextClass.LARGE: "deep"}[context_class],
        max_parallel_workers=parallel_cap,
        prompt_detail={ContextClass.SMALL: "compact", ContextClass.MEDIUM: "balanced", ContextClass.LARGE: "comprehensive"}[context_class],
        verification_frequency={ContextClass.SMALL: "every_step", ContextClass.MEDIUM: "every_phase", ContextClass.LARGE: "phase_and_closeout"}[context_class],
        checkpoint_interval_steps=memory.checkpoint_every_steps,
        evidence_level="full" if cap.reasoning is True or context_class == ContextClass.LARGE else "essential",
        max_retries=2 if cap.local is True else 3,
    )

    return AdaptiveRuntimeProfile(
        profile_id=f"{context_class.value}-{memory_mode.value}",
        provider=cap.provider,
        model=cap.model,
        capabilities=cap,
        context=context,
        memory=memory,
        worker=worker,
        checkpoint_strategy=f"checkpoint_every_{memory.checkpoint_every_steps}_steps",
        retrieval_strategy="semantic_then_repository" if cap.embeddings is True else ("repository_first" if context.retrieval_first else "in_context_first"),
        conversation_strategy=f"history_{context.history_message_limit}_{context.summarization}_summary",
        execution_strategy=f"batch_{context.task_batch_size}_parallel_{worker.max_parallel_workers}",
        fallback_strategy="capability_compatible_tier_then_provider",
    )


class AdaptiveRuntimeRegistry:
    """In-process source of truth for detected model profiles."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], AdaptiveRuntimeProfile] = {}
        self._active: tuple[str, str] | None = None

    def register(self, capabilities: ModelCapabilities) -> AdaptiveRuntimeProfile:
        profile = generate_runtime_profile(capabilities)
        key = (capabilities.provider, capabilities.model)
        self._profiles[key] = profile
        self._active = key
        return profile

    def get(self, provider: str, model: str) -> AdaptiveRuntimeProfile | None:
        return self._profiles.get((provider, model))

    def active(self) -> AdaptiveRuntimeProfile | None:
        return self._profiles.get(self._active) if self._active else None

    def all(self) -> list[dict[str, Any]]:
        return [profile.to_dict() for profile in self._profiles.values()]


adaptive_runtime = AdaptiveRuntimeRegistry()


def conservative_profile(provider: str = "unconfigured", model: str = "unconfigured") -> AdaptiveRuntimeProfile:
    return generate_runtime_profile(capabilities_from_metadata(provider, model, None))


def apply_worker_policy(task_context: Mapping[str, Any], profile: AdaptiveRuntimeProfile) -> dict[str, Any]:
    """Attach immutable adaptive policy data without mutating caller context."""
    result = dict(task_context)
    result["adaptive_runtime"] = {
        "profile_id": profile.profile_id,
        "context": asdict(profile.context),
        "memory": asdict(profile.memory),
        "worker": asdict(profile.worker),
        "checkpoint_strategy": profile.checkpoint_strategy,
    }
    return result


def runtime_prompt_directive(profile: AdaptiveRuntimeProfile) -> str:
    """Human-readable worker directive derived only from active policies."""
    w = profile.worker
    c = profile.context
    return (
        "--- ADAPTIVE RUNTIME POLICY ---\n"
        f"Context class: {c.classification}; prompt detail: {w.prompt_detail}.\n"
        f"Planning: {w.planning_depth}; verification: {w.verification_frequency}.\n"
        f"Checkpoint every {w.checkpoint_interval_steps} execution step(s).\n"
        f"Use at most {w.max_parallel_workers} parallel worker request(s).\n"
        f"Retrieval first: {'yes' if c.retrieval_first else 'no'}; "
        f"history limit: {c.history_message_limit} messages."
    )
