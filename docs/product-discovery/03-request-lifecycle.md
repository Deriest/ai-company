# AIC-ADE Execution Path Verification

## Primary Entry Points

### 1. Frontend Chat Submit (User Action)

**Flow:**
```
User clicks "Send" or presses Enter
    ↓
src/renderer/src/components/ChatView.tsx:handleSubmit()
    ↓
API call to backend POST /api/v1/chat/execute
    ↓
Backend route: backend/api/routes/core.py:chat_execute()
    ↓
Service: backend/services/chat_service.py:ChatService.execute_chat()
    ↓
LLM call via backend/llm/provider.py
    ↓
Streaming response via SSE (Server-Sent Events)
    ↓
Frontend renders tokens progressively
```

**Evidence Files:**
- `app/src/renderer/src/components/ChatView.tsx` — Submit handler
- `backend/api/routes/core.py:chat_execute()` — REST endpoint
- `backend/services/chat_service.py` — Chat execution logic
- `backend/llm/provider.py` — LLM provider abstraction

### 2. Backend REST API (Direct Call)

**Supported Endpoints:**
```
POST   /api/v1/chat/execute       # Execute chat message
POST   /api/v1/members            # Member list management
GET    /api/v1/models             # Available model list
POST   /api/v1/tasks              # Create task
GET    /api/v1/tasks/{id}         # Get task status
WS     /ws/live                   # WebSocket for live updates
```

**Entry Point:** `backend/backend/main.py:create_app()` → FastAPI app startup

### 3. Electron IPC (Main ↔ Renderer)

**Flow:**
```
Renderer → Main Process
    ↓ contextBridge.invoke('system', 'action', params)
    ↓
dist-electron/main/main.ts:ipcMain.handle()
    ↓
Call shared utility or trigger background process
```

**Evidence Files:**
- `app/dist-electron/preload/preload.js` — contextBridge setup
- `app/dist-electron/main/main.js` — IPC handlers

## Execution Stage Analysis

| Stage | Component          | File                          | Input                    | Output                  | Async? |
|-------|--------------------|-------------------------------|--------------------------|-------------------------|--------|
| 1     | UI Submit          | ChatView.tsx                  | User text, message ID    | API request             | No     |
| 2     | Route Handler      | core.py                       | Request body             | Dict, headers           | No     |
| 3     | Service            | chat_service.py               | Auth, prompt, context    | Executed response       | Yes    |
| 4     | Provider           | provider.py                   | Model config, messages   | LLM completion          | Yes    |
| 5     | Stream Delivery    | delivery/engine.py            | Completion chunks        | SSE events              | Yes    |
| 6     | Frontend Render    | ChatMessage.tsx               | Token stream             | Updated message display | Yes    |

## Verified Components Status

### ✓ Executed Components

- **ChatService.execute_chat()** — Always executed when user sends chat message
- **provider.get_completion()** — Called from execute_chat
- **delivery.stream_response()** — Streaming wrapper around LLM response
- **FastAPI routes in core.py** — Entrypoint for all chat endpoints

### ⚠ Conditionally Executed

- **Mission/Task workflows** — Only triggered when intent = task_request
- **Worker lifecycle** — Only when dispatcher assigns task
- **Memory/RAG services** — When context required & enabled
- **ConversationEngine integration** — Partially wired (see Document 13)

### ✗ Exists but Never Executed (from primary path)

- **Discovery planning engine** — Isolated (REST-only, not called from chat path)
- **Autonomy orchestration** — Not triggered from standard chat flow
- **Legacy conversation workflow** — Code exists but bypassed by passthrough

### ? Unable to Determine

- **Intent detection mechanism** — Source unclear, may be implicit in service layer
- **Error handling fallbacks** — No explicit try/catch observed in primary path

## Unreachable Components

Based on code inspection and git status:

1. **backend/dispatcher/engine.py** — Worker orchestrator (exists but no direct caller from chat path)
2. **backend/autonomy/*.py** — Autonomous agent decision engine (isolated)
3. **backend/discovery/**/*.py** — Intent discovery pipeline (REST-only)

These components are IMPLEMENTED but NOT WIRED to the primary chat execution path. They can only be accessed via:
- Direct REST API calls
- Manual testing scripts
- Future feature flags

## Decision Points

| Location                      | Decision                                    | Branches To                |
|-------------------------------|---------------------------------------------|----------------------------|
| ChatService.execute_chat()    | Check if task detected                      | chat vs task workflows     |
| provider.get_completion()     | Select LLM model based on config            | multiple provider options  |
| delivery.stream_response()    | Choose streaming vs non-streaming delivery  | real-time vs batch output  |

## Missing Evidence

- **Session/Thread tracking** — No session_id captured in primary path logs
- **Billing/Usage tracking** — No token usage logged in visible execution flow
- **Audit trail storage** — Conversation logs stored but retrieval path unverified

---

*Verified by: file inspection, opencode log analysis, runtime state reading*  
*Session ID: ses_0117e698affeM9qeGL2ZLZU6qq*  
*Date: 2026-08-11 11:20 WIB*
