# 52 — Model Discovery

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Discovery Flow

```
POST /api/llm/providers/{id}/test
  → ProviderManager.list_models(base_url, api_key)
  → HTTP GET {base_url}/v1/models (OpenAI-compatible)
  → Returns list of model IDs
  → Adaptive runtime: capabilities_from_metadata(provider, model, metadata)
  → Registers profile in AdaptiveRuntimeRegistry
```

## Capability Detection

**Source:** `runtime/adaptive.py:161-204`

| Capability | Detection Source |
|---|---|
| `context_window` | `context_window`, `context_length`, `max_context_tokens` |
| `max_output_tokens` | `max_output_tokens`, `max_completion_tokens`, `output_limit` |
| `tool_calling` | `tool_calling`, `supports_tools`, `supports_tool_calling` |
| `json_mode` | `json_mode`, `supports_json`, `supports_json_mode` |
| `reasoning` | `reasoning`, `supports_reasoning`, `supports_thinking` |
| `streaming` | `streaming`, `supports_streaming` |
| `vision` | `vision`, `supports_vision` |
| `embeddings` | `embeddings`, `supports_embeddings` |
| `function_calling` | `function_calling`, `supports_function_calling` |
| `parallel_requests` | `parallel_requests`, `supports_parallel_requests` |
| `mcp` | `mcp`, `supports_mcp` |
| `local` | `local`, `is_local` |

## Policy Generation

**Source:** `runtime/adaptive.py:207-293`

| Context Class | Window | History | Prompt Budget | Retrieval |
|---|---|---|---|---|
| SMALL | <32K | 6 msgs | 45% of window | retrieval_first=True |
| MEDIUM | 32K-100K | 16 msgs | 55% of window | retrieval_first=True |
| LARGE | ≥100K | 40 msgs | min(64K, 55%) | retrieval_first=False |

| Memory Mode | Condition |
|---|---|
| SESSION_ONLY | No embeddings, small context |
| CHECKPOINT | No embeddings, medium context |
| REPOSITORY | No embeddings, large context |
| SEMANTIC | Embeddings available, any context |
| HYBRID | Embeddings + large context |

## Issues

1. **Most providers return bare model IDs** — no capability metadata in `/v1/models` response. Adaptive runtime falls back to conservative defaults (SMALL context, SESSION_ONLY memory).
2. **No caching** — model discovery makes a live HTTP call every time. Should cache results with TTL.
3. **Provider-specific metadata** — some providers (OpenRouter, custom) include capability metadata; most don't. Detection relies on metadata alias matching.
