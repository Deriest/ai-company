# 32 — Adaptive Runtime Foundation (ADR-006)

---

## ADR-006: v1.7.x Adaptive Runtime Platform

- **Status:** Accepted
- **Context:** In prior versions, LLM interactions hardcoded worker behavior, prompt structures, and context handling regardless of the underlying model's capabilities (e.g., prompt size, tools, embeddings).
- **Decision:** Introduce a capability-driven Adaptive Runtime. 
  1. Extract capability profiles (`ModelCapabilities`) from provider metadata.
  2. Dynamically generate an `AdaptiveRuntimeProfile` mapping model capabilities to `ContextPolicy`, `MemoryPolicy`, and `WorkerPolicy`.
  3. Inject these policies into worker execution contexts (`apply_worker_policy`) and system prompt assembly.
  4. Expose active profiles in the Command Center API and Desktop UI (`ProviderSettings`).
- **Consequences:** Workers and memory systems now dynamically adjust checkpoint intervals, planning depth, and retrieval strategy based on whether the active model is large-context, supports embeddings, or handles complex reasoning. Hardcoded tier mapping is now supplemented by capability constraints.
