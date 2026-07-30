# 24 — API Specification

**Protocol:** REST (JSON) + SSE (EventStream) + WebSockets  
**Base URL:** `http://127.0.0.1:8000/api`  

---

## 1. Key API Endpoints

### Authentication
- `POST /api/auth/login`: Authenticate local session, returns Bearer JWT token.

### Conversations & Chat
- `GET /api/conversations`: List user conversations.
- `POST /api/conversations`: Create a new conversation.
- `PUT /api/conversations/{id}`: Rename or update conversation status.
- `DELETE /api/conversations/{id}`: Permanently delete conversation and messages.
- `GET /api/conversations/{id}/messages`: Retrieve message history.
- `POST /api/conversations/{id}/messages`: Send message (non-streaming).
- `POST /api/conversations/{id}/messages/stream`: Send message with SSE streaming output.

### LLM Providers
- `GET /api/llm/providers`: List registered providers.
- `POST /api/llm/providers`: Register new provider.
- `PUT /api/llm/providers/{id}`: Update provider configuration.
- `POST /api/llm/providers/{id}/activate`: Set active provider.
- `POST /api/llm/providers/{id}/test`: Test endpoint connection and latency.
- `POST /api/llm/providers/probe`: Probe unconfigured endpoint for available models.

### Tasks & Workspace
- `GET /api/tasks`: List tasks.
- `GET /api/tasks/{id}`: Retrieve detailed task state.
- `POST /api/tasks/{id}/dispatch`: Dispatch task to worker.
- `GET /api/tasks/{id}/download`: Download workspace deliverables as ZIP archive.
