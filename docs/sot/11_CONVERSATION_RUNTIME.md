# 11 — Conversation Runtime

**Subsystem:** Chat & SSE Engine  
**Files:** `conversation/engine.py`, `backend/routes/conversations.py`, `App.tsx`  

---

## 1. Conversation Lifecycle & Auto-Titling

1. **Unique Persistent ID:** Each conversation is created with a UUID.
2. **Auto-Titling:** On the user's first prompt, the engine extracts a clean, concise title (e.g. *"Fix JWT Auth"* or *"Explain Mars vs Moon"*). Default titles like "Hermes" or "New Conversation" are prohibited once a prompt is sent.
3. **Instant UI Synchronization:** Renaming, auto-titling, and deletion update state immediately in the desktop UI and persistent database.
4. **SSE Streaming:** Text chunks stream incrementally over Server-Sent Events (`/api/conversations/{id}/messages/stream`) to prevent UI freezing.

---

## 2. Message History Grouping

Conversations in the sidebar are filtered and grouped chronologically:
- **Today**
- **Yesterday**
- **Last Week**
- **Older**
