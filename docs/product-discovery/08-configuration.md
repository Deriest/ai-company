# AIC-ADE Configuration Analysis

## Configuration Layers

### Layer 1: User Settings (Persistent)

| Source                        | Location                              | Scope     | Persistence |
|-------------------------------|---------------------------------------|-----------|-------------|
| Backend config                | `backend/backend/config.py`           | Runtime   | Memory only |
| Frontend config               | `app/src/renderer/src/config/`        | Build     | Local storage |
| Environment variables         | `.env`, `.env.local`                  | Runtime   | File-based  |
| User preferences              | `localStorage` in browser             | Session   | Browser     |

**Key Files:**
- `backend/backend/main.py` — FastAPI app config (CORS, middleware, routes)
- `app/.env.example` — Environment template
- `app/package.json` — Electron build & runtime config

---

### Layer 2: Hardcoded Defaults

| Setting                    | Default Value       | Override Method      |
|----------------------------|---------------------|----------------------|
| API endpoint               | `http://localhost:8000` | `process.env.VITE_API_URL` |
| Model default              | `9r/qd/qmodel_38max`  | Frontend dropdown    |
| Streaming interval         | `50ms`              | Delivery engine code |
| WebSocket timeout          | `30s`               | Connection init code |
| Max message history        | `50 messages`       | ChatService limit    |

**Evidence from inspection:**
```python
# backend/backend/main.py
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"])
```

```typescript
// app/src/renderer/src/hooks/useChat.tsx
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

---

### Layer 3: Automatic Discovery

| Feature                    | Discovery Mechanism                     | Storage Location           |
|----------------------------|-----------------------------------------|----------------------------|
| Available models           | `/api/v1/models` endpoint call          | Frontend state cache       |
| Provider list              | OAuth registry read                     | `data/providers.json`      |
| Worker capabilities        | Worker registration callback            | Runtime worker pool        |
| Health status              | Periodic `/health` ping                 | In-memory health tracker   |

**Dynamic Sources:**
- `GET /api/v1/models` → Returns available model IDs from provider
- `GET /api/v1/members` → Registered user list
- `backend/storage/models.py` → Database schema definitions

---

### Layer 4: Runtime State

| Component                | Runtime Variable              | Lifetime        | Reset Trigger       |
|--------------------------|-------------------------------|-----------------|---------------------|
| Conversation context     | `session.context_stack`       | Per session     | New chat starts     |
| Worker task queue        | `dispatcher.queue`            | Process life    | Server restart      |
| Auth tokens              | `jwt_token` in header         | Expires at TTL  | Logout or expiry    |
| Event subscriptions      | `event_bus.subscribers`       | Process life    | Unsubscribe call    |

---

## Configuration Management Strategies

### Strategy A: Environment Variables (Dev)

```bash
# .env.local in project root
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=AIC-ADE
BACKEND_PORT=8000
ELECTRON_PORT=5174
JWT_SECRET=dev-secret-change-in-prod
DATABASE_URL=sqlite:///./aic_ade.db
```

### Strategy B: Config File (Prod/Staging)

```yaml
# config.yaml or config.toml format
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  debug: false

database:
  url: postgresql://user:pass@host:5432/aic_ade
  pool_size: 20

models:
  default: "9r/qd/qmodel_38max"
  allowed: ["openai/gpt-4", "anthropic/claude-3"]
```

### Strategy C: Registry-Based (Multi-Tenant)

```json
// data/providers.json
{
  "providers": [
    {
      "id": "custom-aic",
      "name": "AIC Custom",
      "base_url": "https://api.aicompany.biz.id/v1",
      "auth_type": "oauth",
      "enabled": true
    }
  ]
}
```

---

## Key Configuration Points

### 1. Database Path

**Actual location:** `DATA_DIR` env var or hardcoded path in `backend/database/session.py`  
**Default:** `sqlite:///./aic_ade.db`  
**Override:** Set `DATA_DIR=/path/to/data` before starting backend

### 2. CORS & Allowed Origins

**Backend default:** `["http://localhost:5173"]`  
**Frontend dev server:** Usually `http://localhost:5174` (check Vite config)  
**Risk:** Mismatch causes CORS errors in development

### 3. Streaming Configuration

**Stream interval:** Hardcoded in `delivery/engine.py` (typically 50-100ms)  
**Chunk size:** Depends on LLM provider rate limit  
**Retry logic:** Exponential backoff on connection failure

### 4. JWT & Authentication

**Token format:** Standard JWT (header.payload.signature)  
**Expiration:** Typically 24 hours (configurable)  
**Refresh:** Manual re-auth required (no auto-refresh observed)

---

## Configuration Audit Findings

### ✓ Verified Working Configurations

- **Local development setup:** Backend + Frontend both run on localhost
- **Provider selection:** Dropdown in UI maps correctly to backend config
- **Database persistence:** SQLite file created and updated during session

### ⚠ Potential Issues

1. **Missing environment documentation:** No `.env.example` for backend vars
2. **Hardcoded URLs:** Some endpoints use `localhost` instead of dynamic detection
3. **No hot reload:** Changing config requires full restart

### ✗ Missing Capabilities

- **Feature flags system:** No configuration to enable/disable features per-user
- **A/B testing support:** Cannot route subset of users to different models
- **Remote config sync:** Config changes not synced across sessions/devices

---

*Configuration inspected via:* source code review, runtime log analysis, git diff verification  
*Date: 2026-08-11 11:22 WIB*
