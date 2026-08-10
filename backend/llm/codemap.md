# Backend LLM Module Codemap

**Module Path:** `/home/tvd/AI-Company/backend/llm/`  
**Last Updated:** 2026-08-10  
**Analysis Scope:** All `.py` files excluding `**/*.test.py`, `conftest.py`, and `.venv/` directories

---

## 1. Responsibility

The `backend/llm` directory implements an **LLM Provider Abstraction Layer** that serves as a unified interface for interacting with diverse large language model providers. The module provides a vendor-neutral API for chat completions, streaming responses, and model discovery while abstracting provider-specific quirks, authentication schemes, and API format variations.

### Primary Roles:

| Role | Description |
|------|-------------|
| **Provider Agnostic Gateway** | Supports any OpenAI-compatible API (OpenAI, OpenRouter, vLLM, LM Studio, Ollama, 9router, vansrouter) through a single standardized interface |
| **Smart Worker Routing** | Implements tier-based model selection (thinker/crafter/sprinter) with automatic fallback chains for error resilience across worker types |
| **Usage Tracking & Auditing** | Records token consumption, costs, and usage patterns per provider/model/tier/purpose; persists to SQLite via SQLAlchemy |
| **Multi-Turn Conversation Workaround** | Special handling for problematic gateways (VansRouter bug QA-249-R6) that return empty responses for multi-turn history |
| **Reasoning Model Control** | Environment-driven `reasoning_effort` parameter injection (low/medium/high/auto) with intelligent defaults to avoid unsupported parameters |
| **Concurrency Limiter** | Per-provider async semaphore gating prevents gateway overload and truncation issues during parallel worker phase execution |

### Sub-Domain Responsibilities:

- **Model Tier Management** (`ModelTier` enum, `_worker_fallback_chain`) — Defines four reasoning tiers with deterministic fallback orderings
- **Provider Configuration** (`ProviderConfig` dataclass) — Centralizes model mappings, endpoints, timeouts, retry policies, and special flags
- **HTTP Client Factory** (`httpx.AsyncClient` instantiation) — Generates configured clients with User-Agent spoofing for Cloudflare bypass
- **Response Normalization** — Handles multiple response formats (JSON, SSE chunks, DeepSeek R1 thinking tags, tool_call deltas)
- **Provider Lifecycle** (`ProviderManager`) — Registration, active provider switching, deregistration with client cleanup

---

## 2. Design Patterns

### Pattern Catalog by Category

#### 2.1 Architectural Patterns

| Pattern | Location | Implementation Details |
|---------|----------|------------------------|
| **Provider Pattern (Registry)** | `ProviderManager`, `_providers: dict[str, LLMProvider]` | Maintains runtime registry of registered LLM providers. Each provider implements identical interface but differs in base_url, api_key, models, timeout. Dynamic addition/removal without restart. |
| **Strategy (Tier Selection)** | `_worker_fallback_chain()`, `chat(tier=...)` | Runtime strategy selection based on task complexity. Three strategies (thinker/crafter/sprinter) each with predefined fallback chains. Unknown tiers resolve to CRAFTER default. |
| **Factory Method** | `init_provider_from_env()` | Constructs `ProviderConfig` from environment variables with sensible defaults. Separates configuration assembly from provider instantiation. Enables dependency-free initialization. |
| **Singleton** | `usage_tracker = UsageTracker()`, `provider_manager = ProviderManager()` | Global state management for usage tracking and provider registry. Module-level instantiation ensures consistent state across application domains. |
| **Decorator (Async Context Manager)** | `async with self._sem():` | Concurrency limiting via semaphore wrapping. Limits outbound concurrent requests to prevent gateway throttling/truncation. Configurable via `AIC_LLM_MAX_CONCURRENT`. |

#### 2.2 Creational Patterns

| Pattern | Location | Implementation Details |
|---------|----------|------------------------|
| **Builder (Implicit via Dataclass)** | `ProviderConfig` dataclass | Fluent configuration accumulation through field assignments. Defaults provide fallback behavior when env vars absent. `__post_init__` normalizes edge cases (None → {}). |
| **Lazy Initialization** | `self.__sem` (in `LLMProvider._sem()`) | Semaphore created on first call within running event loop. Guards against thread-local event loop access before async context established. |
| **Object Pool (Implicit)** | `UsageTracker._records` sliding window | Automatically trims old records when exceeding 10k entries, retaining only most recent 5k. Memory-bounded usage history retention. |

#### 2.3 Behavioral Patterns

| Pattern | Location | Implementation Details |
|---------|----------|------------------------|
| **Retry Pattern (Exponential Backoff)** | `for attempt in range(self.config.max_retries + 1):` | Retries transient failures (429, 502, 503, 504) with exponential backoff (3×2^attempt seconds). Non-retryable errors (4xx client) break immediately. Connection errors get fixed 2s delay. |
| **Observer (Fire-and-Forget Persistence)** | `UsageTracker.record()` → `_persist()` | Usage records observed at request completion. Async persistence via detached coroutine creation. Handles DB locking contention with max 7 retries, short backoffs. |
| **Template Method (Error Recovery Chain)** | `LLMProvider.chat()` multi-tier retry → fallback provider | Skeleton defines: try tier chain → try fallback provider → raise aggregated error. Concrete steps (model resolution, payload construction, response parsing) implemented once, reused across all attempts. |
| **State Machine (Streaming Yield Loop)** | `LLMProvider.chat_stream()` generator | Generator state machine yielding chunk/type/error/done events. Handles network interruptions, malformed SSE, empty responses via fallback to non-streaming chat(). |

#### 2.4 Structural Patterns

| Pattern | Location | Implementation Details |
|---------|----------|------------------------|
| **Adapter (Response Format Normalizer)** | Response parsing block (lines 380-473), SSE merger | Adapts disparate upstream response formats into unified internal schema. Handles: standard JSON, SSE with delta merging, non-streaming wrappers, missing choices fields, tool_call reconstruction. |
| **Facade (High-Level Chat API)** | `ProviderManager.chat()`, `ProviderManager.chat_stream()` | Simplifies complex provider interactions behind two method signatures. Hides tier routing, fallback chains, active provider selection, API key validation. |
| **Front Controller (Request Entry Point)** | `ProviderManager.get_active_with_key()` | Pre-processing filter before request dispatch. Validates API key presence, prevents "Bearer" header errors from stubbed providers. Selects optimal provider from registry. |

#### 2.5 Database-Specific Patterns

| Pattern | Location | Implementation Details |
|---------|----------|------------------------|
| **Data Mapper (ORM Integration)** | `UsageTracker._persist()` uses `LLMUsageLog` | Maps Python usage records to database rows. SQLAlchemy session manages transaction boundaries, flushes, commits. Identity map ensures session-scoped consistency. |
| **Unit of Work (Transaction Wrapping)** | `async_session() as session:` → `await session.commit()` | Explicit transaction scope around usage record insertion. Atomicity guaranteed or rollback on exception. WAL mode mitigates write contention with main pipeline writes. |

---

## 3. Data & Control Flow

### 3.1 Entry Points and Activation

| Entry Point | Trigger Mechanism | Primary Flow |
|-------------|-------------------|--------------|
| **Environment Initialization** | `init_provider_from_env()` called at startup | Reads AIC_LLM_* env vars → builds `ProviderConfig` → registers with `ProviderManager` |
| **Runtime Provider Registration** | `provider_manager.register(config)` from external modules | Updates internal provider registry, creates new `httpx.AsyncClient`, closes old if replacing |
| **User Request Handling** | `ProviderManager.chat(messages, tier, ...)` from agent_runner/task orchestrator | Resolves active provider → selects tier → constructs payload → makes HTTP request → parses response → tracks usage → returns content |
| **Streaming Consumption** | `async for chunk in ProviderManager.chat_stream(...)` | Yields incremental tokens via async generator. Handles network glitches with fallback to complete response. |

### 3.2 Data Flow Diagrams

#### 3.2.1 Core Chat Request Flow (`LLMProvider.chat()`)

```
[Agent Runner Task] 
      ↓ messages=[system, user, assistant...], tier=THINKER, purpose="planning"
      ↓
[ProviderManager.chat(messages, tier)]
      ├─→ get_active_with_key() → validate API key present
      └─→ _worker_fallback_chain(THINKER) → [THINKER, CRAFTER, SPRINTER]
           ↓
    [LLMProvider.chat()]
         ├─→ config.get_model(THINKER) → "deepseek-r1"
         ├─→ flatten_history check → VansRouter? Yes: compress multi-turn
         └─→ _maybe_set_reasoning_effort(payload, model) → inject "low" if env configured
              ↓
         [Payload Construction]
              {
                  "model": "deepseek-r1",
                  "messages": [...compressed history...],
                  "temperature": 0.7,
                  "reasoning_effort": "low" (optional)
              }
              ↓
         [Semaphore Acquire] → max 4 concurrent outbound requests
              ↓
         [httpx.AsyncClient.post("/chat/completions", json=payload)]
              ↓
         [Upstream Gateway Processing] (OpenAI/OpenRouter/vansrouter/etc.)
              ↓
         [Response Handling]
              ├─→ parse_json() → normalize choices/message/usage
              ├─→ strip_thinking_tags(content) → remove <thinking></thinking>
              ├─→ merge_tool_calls(deltas) → reconstruct function calls
              └─→ streaming fallback if empty body detected
                   ↓
         [Response Normalization]
              {
                  "content": "final answer text",
                  "model": "deepseek-r1",
                  "usage": {"prompt_tokens": 120, "completion_tokens": 340},
                  "raw": full_response_dict
              }
              ↓
         [UsageTracker.record(record)] → fire-and-forget persistence
              ↓
         [Return to Agent Runner] → continue task execution
```

#### 3.2.2 Streaming Token Flow (`LLMProvider.chat_stream()`)

```
[UI Consumer / Frontend]
      ↓ async iteration request
      ↓
[ProviderManager.chat_stream(messages, tier)]
      ↓
[LLMProvider.chat_stream(messages, tier)]
      ├─→ flatten_history check
      ├─→ payload["stream"] = True
      └─→ httpx.AsyncClient.stream("POST", "/chat/completions", json=payload)
           ↓
        [Server-Sent Events Parsing]
             for line in resp.aiter_lines():
                 ├─→ line.startswith("data: ")
                 ├─→ json.loads(data_str)
                 └─→ extract delta.content from choices[0].delta
                      ↓
             [Yield Chunk Generator]
                  yield {"type": "chunk", "content": token_delta}
                      ↓
        [Usage Record Creation on Completion]
             record = UsageRecord(...)
             usage_tracker.record(record)
                  ↓
        [Final Yield]
             yield {"type": "done", "model": m, "usage": {}}
```

#### 3.2.3 Fallback Chain Logic Flow (`_worker_fallback_chain()`)

```
[Caller: ProviderManager.chat()]
      ↓ tier = THINKER
      ↓
[_worker_fallback_chain(THINKER)]
      ├─→ lookup _WORKER_FALLBACK_CHAINS["thinker"]
      └─→ return [THINKER, CRAFTER, SPRINTER]
           ↓
    [Iterative Attempt Loop]
         for t in [THINKER, CRAFTER, SPRINTER]:
              try:
                   await provider.chat(tier=t)
                   return result
              except LLMError:
                   last_error = e
                   log.warning(f"Tier {t} failed...")
         ↓ (all tiers failed on primary provider)
    [Secondary Provider Check]
         cfg = _configs.get(primary_provider_name)
         if cfg.fallback_provider:
              fallback = _providers[cfg.fallback_provider]
              for t in tiers_to_try:
                   try: return fallback.chat(tier=t)
                   except: last_error = e
         ↓ (no fallback provider configured)
    [Exception Propagation]
         raise last_error OR LLMError("All attempts exhausted")
```

#### 3.2.4 History Flattening Workaround (`_flatten_history()`)

```
[VansRouter Multi-Turn Request]
      ↓ messages=[sys, usr1, ass1, usr2, ass2, usr3] (6 messages)
      ↓
[_flatten_history(messages)]
      ├─→ len(messages) > 2? YES
      ├─→ has tool_calls in any message? NO (skip flattening guard)
      ├─→ separate system_messages + other_messages
      ├─→ last_message = other_messages[-1] (usr3)
      ├─→ history_messages = other_messages[:-1] (usr1, ass1, usr2, ass2)
      └─→ build compressed system:
              "SYS_PROMPT\n\n## Conversation History\nuser: usr1\nassistant: ass1\nuser: usr2\nassistant: ass2\n"
                   ↓
    [Flattened Payload Sent to VansRouter]
         messages=[
             {"role": "system", "content": "[full conversation]"},
             {"role": "user", "content": "usr3"}
         ]
```

### 3.3 State Management Strategies

| Approach | Location | Characteristics |
|----------|----------|-----------------|
| **In-Memory Active Provider Registry** | `ProviderManager._providers: dict[str, LLMProvider]` | Mutable dictionary keyed by provider name. Lazy population from registration events. Thread-safe reads but async-safe removal required. |
| **Event Loop Bound Concurrency Semaphores** | `LLMProvider._sem()` → `asyncio.Semaphore` | Created lazily on first use within running loop. Re-created if event loop changes (worker migration). Default limit 4 concurrent requests. |
| **Sliding Window Usage Records** | `UsageTracker._records: list[UsageRecord]` | Auto-trims oldest 5k when >10k entries retained. Lock-protected appends (`threading.Lock`). Asynchronous persistence drops heavy IO pressure from main request path. |
| **Configuration Immutability (Post-Init)** | `ProviderConfig` dataclass | `__post_init__()` normalizes None values → {} for models dict. Immutable after instantiation except for provider manager's dynamic replacements. |

### 3.4 Error Propagation Paths

| Failure Mode | Detection Layer | Propagation Strategy | Recovery |
|--------------|-----------------|---------------------|----------|
| **Empty Model Name** | `if not model: raise LLMError(...)` | Immediate `LLMError` with clear UI directive ("Select a model in Settings > Providers") | User must reconfigure provider before retry |
| **Network Connectivity Loss** | `httpx.ConnectError`, `httpx.TimeoutException` | Catch → log warning → sleep → retry up to max_retries count | Automatic retry with 1s base delay; eventually surface error to caller |
| **Rate Limiting (429)** | `e.response.status_code == 429` | Exponential backoff sleep (3×2^attempt seconds) before retry | Retry same tier/provider after sufficient wait; may succeed after quota reset |
| **Gateway Overload (502/503/504)** | Server-side proxy errors | Exponential backoff with 2s minimum delay between attempts | Retry cascade may succeed if gateway recovers mid-backoff |
| **Malformed JSON Response** | `json.JSONDecodeError` during parsing | Attempts SSE fallback, then brace-matching substring extraction | Partial recovery via alternative parsing strategies; fails gracefully if all fail |
| **Missing Choices Field** | `if not choices: raise LLMError(...)` | Structured error with raw response keys for debugging | Upstream provider misconfiguration; requires backend fix |
| **API Key Missing (Empty Header)** | `get_active_with_key()` null key detection | Skips unkeyed providers; falls back to next registered provider with key | Silent provider rotation; no user interruption unless ALL providers lack keys |
| **DB Write Locked** | `OperationalError("database is locked")` | 7 retries with 50ms×attempt exponential backoff | Background persistence absorbs contention; main flow continues unaffected |

---

## 4. Integration Points

### 4.1 External Dependencies (Import Statements Analysis)

| Import Source | Modules Using | Purpose |
|---------------|---------------|---------|
| `httpx` | `provider.py` lines 24, 290, 616 | Async HTTP client for provider API calls. Session reuse via `httpx.AsyncClient`. |
| `runtime.adaptive` | `provider.py` lines 26, 276, 782 | Adaptive runtime profiling integration. Registers discovered model capabilities via `capabilities_from_metadata()`. |
| `sqlalchemy.exc` | `provider.py` lines 189, 208 | OperationalError detection for database locking scenarios. |
| `storage.database` | `provider.py` lines 193, 196 | SQLAlchemy async session factory (`async_session()`). |
| `storage.models` | `provider.py` lines 194, 196 | LLMUsageLog ORM model definition for usage persistence. |
| `backend.config.settings` | `provider.py` lines 1108, 1158 | Environment variable fallback source when process-level env vars unavailable. |
| `dataclasses` | `provider.py` lines 14, 103 | Type-safe configuration containers (`ProviderConfig`, `UsageRecord`). |
| `enum.Enum` | `provider.py` line 16, 31 | Strongly typed model tier enumeration (`ModelTier`). |
| `logging` | `provider.py` lines 19, 28 | Application-wide logger integration with `"aic.llm"` namespace. |
| `os.environ` | `provider.py` lines 20, 86, 1110 | Runtime configuration override via environment variables (AIC_LLM_*). |
| `asyncio` | `provider.py` lines 22, 174, 298 | Async context management, semaphore implementation, task scheduling. |
| `threading.Lock` | `provider.py` lines 162, 223 | Synchronization for thread-safe usage record storage. |

### 4.2 Consumer Modules (Direct Integrators)

Based on import direction and architectural placement, the following external modules consume `backend.llm`:

| Target Integration | Candidate Files | Integration Points |
|--------------------|-----------------|-------------------|
| **Agent Orchestrator** | `backend/agent_runner/` (implied), task schedulers | Invokes `ProviderManager.chat(messages, tier=THINKER/CRAFTER/SPRINTER, purpose="planning"/"coding"/"review")` for decision-making and code generation. |
| **Conversation Pipeline** | `backend/conversation/` | Uses `ProviderManager.chat_stream()` for real-time chat interfaces. Consumes async chunk generator for WebSocket/SSE delivery. |
| **Web API Endpoints** | `backend/routes/*` | RESTful `/api/chat`, `/api/providers/list`, `/api/providers/register` handlers delegate to provider manager methods. |
| **Admin Dashboard** | Electron main process (environment stamping) | Initializes default provider via `init_provider_from_env()` at application spawn time. Syncs settings changes back to DB. |
| **Usage Analytics** | `storage.models.LLMUsageLog` reader | Periodic aggregation of usage records for billing dashboards, cost tracking, model effectiveness analysis. |

### 4.3 Shared Utility Interfaces

These modules provide reusable abstractions to consumers:

| Interface | Exports | Contract Summary |
|-----------|---------|------------------|
| `ProviderManager.chat()` | `async def chat(messages, tier, temperature, max_tokens, purpose, **kwargs) → dict` | Single-point-of-failure protection with tier fallback. Returns normalized response with content/model/usage/raw. |
| `ProviderManager.chat_stream()` | `async def chat_stream(messages, tier, ...) → AsyncGenerator[dict]` | Incremental token streaming via yield. Emits `{type: "chunk", content: str}` repeatedly, finalizing with `{type: "done"}`. |
| `ProviderManager.list_models()` | `async def list_models() → list[dict]` | Discovers available models from provider endpoint. Normalizes OpenAI/Ollama format differences into canonical form. |
| `ProviderManager.register()/unregister()` | `def register(config: ProviderConfig)`, `async def unregister(name: str)` | CRUD-style lifecycle management. Hot-swaps providers without restart, closes stale httpx clients properly. |
| `UsageTracker.summary()/recent()` | `def summary(since=None) → dict`, `def recent(limit=50) → list[dict]` | Read-only reporting interfaces for analytics dashboards. No state mutation, lock-protected for thread safety. |

### 4.4 Cross-Module Communication Gaps

| Gap Type | Observations | Recommendation |
|----------|--------------|----------------|
| **Sync/Async Mismatch** | `register()` is sync but must close old `httpx.AsyncClient` via `loop.create_task(old.close())`; may leak if no event loop exists | Consider making all ProviderManager methods async (`aregister()`, `aunregister()`) for consistency |
| **Hard-Coded Base URL Fallbacks** | `init_provider_from_env()` uses `default_factory=lambda: {...}` with hardcoded model names ("kc/nvidia/nemotron...") | Parameterize defaults via settings rather than implicit constants; enables cleaner testing overrides |
| **No Versioned API Contracts** | `chat()` and `chat_stream()` accept `**kwargs` pass-through without schema validation | Define explicit request/response schemas (Pydantic) to catch breaking changes early |
| **Usage Record Schema Rigidity** | `UsageRecord` lacks optional fields like `cache_hit`, `latency_ms`, `retry_count` | Extend schema incrementally; mark backward-compatibility migration plan for database alterations |
| **Test Isolation Difficulty** | Singleton `provider_manager` and `usage_tracker` persist across test runs | Provide `reset_test_state()` utility to clear registry and usage records between pytest fixtures |

---

## Appendix: File Inventory Summary

### Total Counts
- **Python Files:** 2 files
  - `__init__.py`: Empty module marker
  - `provider.py`: 1,180 lines of production code
- **Classes Defined:** 4 major classes (`ModelTier`, `ProviderConfig`, `UsageRecord`, `UsageTracker`, `LLMProvider`, `ProviderManager`)
- **Functions Defined:** 7 standalone functions (`_worker_fallback_chain`, `_is_vansrouter_provider`, `_maybe_set_reasoning_effort`, `_flatten_history`, `init_provider_from_env`, `_env_models_for_base_url`, plus class methods)
- **Enum Variants:** 4 (`THINKER`, `CRAFTER`, `SPRINTER`, `VISION`)
- **Environment Variables Consumed:** 10+ (`AIC_LLM_*`, `AIC_MODEL_*`, `AIC_LLM_MAX_CONCURRENT`, `AIC_LLM_REASONING_EFFORT`)

### Directory Structure Hierarchy

```
backend/llm/
├── __init__.py                          # Module initialization (empty)
├── provider.py                          # Core LLM abstraction layer
│   ├── Enum Definitions
│   │   └── ModelTier                    # 4-tier model classification
│   ├── Data Classes
│   │   ├── ProviderConfig               # Configuration container
│   │   └── UsageRecord                  # Token usage audit trail
│   ├── Classes
│   │   ├── UsageTracker                 # Singleton usage aggregator
│   │   ├── LLMProvider                  # Single-provider HTTP client wrapper
│   │   └── ProviderManager              # Multi-provider registry + router
│   ├── Standalone Functions
│   │   ├── _worker_fallback_chain       # Tier fallback logic
│   │   ├── _is_vansrouter_provider      # VansRouter detection heuristic
│   │   ├── _maybe_set_reasoning_effort  # Reasoning param injection
│   │   ├── _flatten_history             # Multi-turn compression workaround
│   │   ├── init_provider_from_env       # Environment config builder
│   │   └── _env_models_for_base_url     # Env-to-provider model mapping
│   └── Module-Scope Constants
│       ├── _WORKER_FALLBACK_CHAINS      # Hardcoded fallback orders
│       ├── _REASONING_EFFORT            # Environment-derived reasoning control
│       ├── usage_tracker                # Global singleton instance
│       └── provider_manager             # Global singleton registry
└── codemap.md                           # This technical specification document
```

---

## Notes on Development Status

This module exhibits characteristics of a **production-grade middleware layer**:

1. **Bug Fix Comments:** Inline QA comments reference specific issue IDs (QA-249-R6, QA-E2E FIX, QA-2441) indicating active maintenance cycle with regression prevention measures
2. **Defensive Programming:** Extensive validation guards (empty models, empty API keys, malformed JSON) with user-friendly error messages rather than opaque stack traces
3. **Graceful Degradation:** Multiple fallback mechanisms (tier chains → secondary providers → streaming retries → SSE parsing → brace-matching JSON extraction) ensure availability under adverse conditions
4. **Observability First:** Comprehensive usage tracking integrated at call sites, persisted asynchronously to enable operational dashboards and billing reconciliation
5. **Future-Proofing:** OpenAI-compatible abstraction allows easy addition of new providers (Gemini, Anthropic adapters) without modifying consumer codebases

Recommended next steps for hardening:
1. Add input validation schemas for chat messages (role/content type checks)
2. Implement circuit breaker pattern for persistent provider outages
3. Extract response normalization into dedicated helper module for better testability
4. Document supported model features per provider (tool calling, multimodal support, native streaming)
5. Consider adding telemetry metrics exporter (OpenTelemetry/StatsD) alongside database logs
