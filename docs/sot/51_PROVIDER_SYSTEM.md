# 51 — Provider System

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Architecture

```
User Config (ProviderSettings.tsx)
  → POST /api/llm/providers
  → LLMProviderConfig (SQLite)
  → ProviderManager (in-memory runtime)
  → ProviderAdapter (OpenAI-compatible HTTP)
  → LLM Response (chat completion)
```

## Provider Data Model

**Source:** `storage/models.py:365-397`

| Field | Type | Purpose |
|---|---|---|
| `id` | str (uuid) | Unique identifier |
| `name` | str | Provider name (e.g., "openai", "anthropic", "custom") |
| `base_url` | str | API base URL |
| `api_key` | str | API key (plaintext in local SQLite) |
| `models` | dict | Tier→model mapping: `{"thinker": "...", "crafter": "...", "sprinter": "..."}` |
| `is_active` | bool | Whether this is the active provider |
| `fallback_provider` | str | Name of fallback provider |
| `timeout` | int | Request timeout in seconds (default: 120) |

## Model Tiers

| Tier | Purpose | Typical Model |
|---|---|---|
| `thinker` | Complex reasoning, planning, architecture | GPT-4, Claude Opus |
| `crafter` | General coding, implementation | GPT-4o, Claude Sonnet |
| `sprinter` | Quick tasks, simple generation | GPT-4o-mini, Claude Haiku |

## Provider API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/llm/providers` | List all providers |
| `POST` | `/api/llm/providers` | Create provider |
| `PUT` | `/api/llm/providers/{id}` | Update provider |
| `DELETE` | `/api/llm/providers/{id}` | Delete provider |
| `POST` | `/api/llm/providers/{id}/activate` | Set as active |
| `POST` | `/api/llm/providers/{id}/test` | Test connection + list models |
| `GET` | `/api/llm/models` | List available models from active provider |

## Fallback Chain

```
Active Provider → chat() call
  → If 429/529/503/timeout: retry with exponential backoff (3 attempts)
  → If all retries fail: fallback_provider.chat()
  → If fallback fails: return error to caller
```

**Source:** `llm/provider.py`

## Provider Registration Flow

1. User submits provider config via UI
2. Backend creates `LLMProviderConfig` in SQLite
3. Backend creates `ProviderConfig` and calls `provider_manager.aregister(cfg)`
4. ProviderManager stores config, sets active if requested
5. Adaptive runtime discovers capabilities from model metadata
6. Capabilities stored in `AdaptiveRuntimeRegistry`

## Issues

1. **API keys stored plaintext** — acceptable for local-first, but should document security boundary clearly
2. **No provider health monitoring** — provider failures are detected only at request time
3. **Model discovery** (`/api/llm/models`) depends on provider adapter supporting `list_models()` — not all adapters implement this
4. **Tier mapping is confusing** — `models` dict uses tier names as keys, but users may want multiple models per tier or custom tier names
