"""Tests for the Adaptive Runtime Profile and Capability extraction."""

from runtime.adaptive import (
    ModelCapabilities,
    capabilities_from_metadata,
    generate_runtime_profile,
    adaptive_runtime,
    ContextClass,
    MemoryMode,
)


def test_capabilities_from_metadata_conservative():
    # Provide no metadata, expect conservative defaults
    cap = capabilities_from_metadata("openai", "gpt-4")
    assert cap.provider == "openai"
    assert cap.model == "gpt-4"
    assert cap.context_window is None
    assert cap.tool_calling is None
    assert cap.source == "conservative_default"


def test_capabilities_from_metadata_rich():
    metadata = {
        "context_length": 128000,
        "max_output_tokens": 4096,
        "supports_tools": True,
        "reasoning": False,
        "vision": "1",
    }
    cap = capabilities_from_metadata("anthropic", "claude-3-opus", metadata, source="discovery")
    assert cap.context_window == 128000
    assert cap.max_output_tokens == 4096
    assert cap.tool_calling is True
    assert cap.reasoning is False
    assert cap.vision is True
    assert cap.source == "discovery"


def test_generate_runtime_profile_large_context():
    cap = ModelCapabilities(
        provider="test",
        model="big",
        context_window=100000,
        embeddings=True,
    )
    profile = generate_runtime_profile(cap)
    
    # Large context should map to ContextClass.LARGE and HYBRID memory (since embeddings=True)
    assert profile.context.classification == "large"
    assert profile.memory.mode == "hybrid_memory"
    assert profile.worker.planning_depth == "deep"
    assert profile.context.retrieval_first is False
    assert profile.checkpoint_strategy == "checkpoint_every_10_steps"


def test_generate_runtime_profile_small_context():
    cap = ModelCapabilities(
        provider="test",
        model="small",
        context_window=4096,
        embeddings=False,
    )
    profile = generate_runtime_profile(cap)
    
    # Small context
    assert profile.context.classification == "small"
    assert profile.memory.mode == "session_only"
    assert profile.worker.planning_depth == "incremental"
    assert profile.context.retrieval_first is True


def test_adaptive_runtime_registry():
    cap = ModelCapabilities(provider="local", model="test-1")
    adaptive_runtime.register(cap)
    
    profile = adaptive_runtime.get("local", "test-1")
    assert profile is not None
    assert profile.provider == "local"
    assert profile.model == "test-1"

    active = adaptive_runtime.active()
    assert active is not None
    assert active.provider == "local"

    all_p = adaptive_runtime.all()
    assert len(all_p) > 0
    assert all_p[-1]["provider"] == "local"
