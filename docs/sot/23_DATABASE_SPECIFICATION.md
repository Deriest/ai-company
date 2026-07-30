# 23 — Database Specification

**Database Engine:** SQLite 3 (Async SQLAlchemy + `aiosqlite`)  
**File Location:** `aic-platform/data/aic.db`  

---

## 1. Table Schemas

### `projects`
- `id` (PK, String): Project UUID.
- `name` (String, Not Null): Project display name.
- `description` (Text): Detailed project description.
- `path` (String): Local directory path on host OS.
- `status` (String): `active` | `archived`.
- `context` (JSON): Metadata, health scores, active worker states.

### `conversations`
- `id` (PK, String): Conversation UUID.
- `project_id` (FK -> projects.id): Associated project.
- `user_id` (FK -> users.id): Conversation owner.
- `title` (String): Automatically derived conversation title.
- `context` (JSON): Last intent, pending task proposals, status.

### `messages`
- `id` (PK, String): Message UUID.
- `conversation_id` (FK -> conversations.id): Message thread.
- `role` (String): `user` | `assistant` | `system`.
- `content` (Text): Response text or prompt.
- `intent` (String): Classified intent.
- `meta` (JSON): Token usage, provider, model, latency.

### `tasks`
- `id` (PK, String): Task UUID.
- `project_id` (FK -> projects.id): Associated project.
- `title` (String): Task title.
- `task_type` (String): `feature` | `bugfix` | `refactor` | `docs` | `test` | `infra` | `research`.
- `worker_type` (String): Target assigned worker role.
- `status` (String): FSM state.
- `progress` (Integer): Progress percentage (0-100).

### `llm_providers`
- `id` (PK, String): Provider UUID.
- `name` (String, Unique): Provider display name.
- `base_url` (String): OpenAI-compatible endpoint URL.
- `api_key` (String): Encrypted API key.
- `models` (JSON): Dict mapping tier names (`thinker`, `crafter`, `sprinter`) to model IDs.
- `is_active` (Boolean): Active provider flag.
