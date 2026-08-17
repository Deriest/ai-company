# 16 — Event Runtime

**Subsystem:** WebSocket & Internal Event Bus  
**Files:** `backend/main.py`, `src/renderer/src/lib/runtimeClient.ts`  

---

## 1. Event Bus Architecture

AIC-ADE uses a dual event notification mechanism:
1. **WebSocket (`ws://127.0.0.1:8000/ws/general`):** Broadcasts real-time events to the desktop UI for instant view updates (tasks, worker activity, status changes).
2. **Server-Sent Events (`/api/conversations/{id}/messages/stream`):** Dedicated token streaming channel for chat responses.
