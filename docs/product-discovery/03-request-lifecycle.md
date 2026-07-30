# 03 — REQUEST LIFECYCLE

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
3.1 OVERVIEW
==================================================

This document reverse engineers the complete request lifecycle from user prompt to final response.

Repository evidence:
- aic-platform/backend/services/chat_service.py
- aic-platform/backend/routes/conversations.py
- aic-platform/backend/api/routes/core.py

==================================================
3.2 STAGE 1: USER INPUT
==================================================

Purpose: User types a message in the Chat interface
Input: User text input
Output: HTTP POST request to /chat or /chat/stream
Owner: Frontend (ChatView.tsx)
Next stage: API Route Handler

Repository evidence:
- aic-ide/src/renderer/src/components/ChatView.tsx — Message composer
- aic-ide/src/renderer/src/lib/api/conversations.ts — API client

==================================================
3.3 STAGE 2: API ROUTE HANDLER
==================================================

Purpose: Receive and validate the chat request
Input: HTTP POST request with message content
Output: Validated request object
Owner: FastAPI route handler
Next stage: Chat Service

Repository evidence:
- aic-platform/backend/api/routes/core.py — @router.post("/chat")
- aic-platform/backend/api/routes/core.py — @router.post("/chat/stream")

==================================================
3.4 STAGE 3: CONVERSATION MANAGEMENT
==================================================

Purpose: Load or create conversation, store user message
Input: Conversation ID, message content
Output: Message object stored in database
Owner: Conversation service
Next stage: Context Assembly

Repository evidence:
- aic-platform/backend/services/chat_service.py — _get_or_create_conversation()
- aic-platform/backend/models/conversation.py — Message model
- aic-platform/backend/routes/conversations.py — Conversation CRUD

==================================================
3.5 STAGE 4: CONTEXT ASSEMBLY
==================================================

Purpose: Build context for the AI prompt
Input: Conversation ID, user query, token budget
Output: Formatted context string
Owner: Context Engine
Next stage: Provider Selection

Repository evidence:
- aic-platform/backend/services/chat_service.py — build_chat_context()
- aic-platform/context/builder.py — ContextBuilder
- aic-platform/context/pipeline.py — ContextPipeline
- aic-platform/context/sources.py — Context sources

CONTEXT SOURCES:
1. Conversation history (messages)
2. Memory entries (relevant memories)
3. RAG documents (knowledge base)
4. Workspace files (project context)

Repository evidence:
- aic-platform/context/sources.py — ConversationSource, MemorySource, RAGSource, WorkspaceSource

==================================================
3.6 STAGE 5: PROVIDER SELECTION
==================================================

Purpose: Select the AI provider and model
Input: Provider ID, model ID
Output: Provider configuration (base_url, api_key)
Owner: Provider service
Next stage: LLM Request

Repository evidence:
- aic-platform/backend/services/chat_service.py — _get_provider_config()
- aic-platform/backend/models/schema.py — Provider model
- aic-platform/backend/services/provider_client.py — Provider client

==================================================
3.7 STAGE 6: LLM REQUEST
==================================================

Purpose: Send request to the AI provider
Input: Messages array, tools schema, provider config
Output: AI response (text or tool calls)
Owner: LLM Provider (external)
Next stage: Response Processing

Repository evidence:
- aic-platform/backend/services/chat_service.py — _stream_chat()
- aic-platform/llm/provider.py — LLM provider abstraction
- aic-platform/backend/services/provider_client.py — HTTP client

REQUEST FORMAT:
{
  "model": "model-id",
  "messages": [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user message"}
  ],
  "tools": [...],  // Optional tool definitions
  "stream": true/false
}

Repository evidence:
- aic-platform/backend/services/chat_service.py — _build_tools_schema()

==================================================
3.8 STAGE 7: TOOL EXECUTION (IF APPLICABLE)
==================================================

Purpose: Execute tool calls requested by the AI
Input: Tool call object (name, arguments)
Output: Tool result
Owner: Tool Dispatcher
Next stage: Continue LLM conversation

Repository evidence:
- aic-platform/backend/services/tool_dispatcher.py — ToolDispatcher
- aic-platform/backend/services/chat_service.py — _execute_tool_call()

AVAILABLE TOOLS:
1. read_file — Read workspace file
2. write_file — Write workspace file
3. search_files — Search workspace files
4. execute_command — Execute shell command

Repository evidence:
- aic-platform/backend/services/chat_service.py — _build_tools_schema()

==================================================
3.9 STAGE 8: ARTIFACT EXTRACTION
==================================================

Purpose: Extract artifacts from AI response
Input: AI response text
Output: Artifact objects (code blocks, file references)
Owner: Artifact Service
Next stage: Response Storage

Repository evidence:
- aic-platform/backend/services/artifact_service.py — ArtifactService
- aic-platform/backend/models/ai_runtime.py — Artifact model

==================================================
3.10 STAGE 9: RESPONSE STORAGE
==================================================

Purpose: Store AI response in database
Input: AI response text, artifacts
Output: Message object stored in database
Owner: Conversation service
Next stage: Response Streaming

Repository evidence:
- aic-platform/backend/services/chat_service.py — store message
- aic-platform/backend/models/conversation.py — Message model

==================================================
3.11 STAGE 10: RESPONSE STREAMING
==================================================

Purpose: Stream response to frontend
Input: AI response chunks
Output: SSE (Server-Sent Events) stream
Owner: FastAPI streaming response
Next stage: Frontend display

Repository evidence:
- aic-platform/backend/services/chat_service.py — stream_chat()
- aic-platform/backend/api/routes/core.py — StreamingResponse

==================================================
3.12 STAGE 11: FRONTEND DISPLAY
==================================================

Purpose: Display response to user
Input: Response chunks
Output: Rendered message in chat
Owner: Frontend (ChatView.tsx)
Next stage: User interaction

Repository evidence:
- aic-ide/src/renderer/src/components/ChatView.tsx — MessageBubble
- aic-ide/src/renderer/src/lib/api/conversations.ts — Streaming client

==================================================
3.13 COMPLETE LIFECYCLE DIAGRAM
==================================================

User types message
       │
       ▼
┌─────────────────┐
│  ChatView.tsx   │
│  (Frontend)     │
└────────┬────────┘
         │ HTTP POST /chat/stream
         ▼
┌─────────────────┐
│  API Route      │
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Conversation   │
│  Management     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Context        │
│  Assembly       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Provider       │
│  Selection      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Request    │
│  (External)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tool Execution │
│  (If needed)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Artifact       │
│  Extraction     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │
│  Storage        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │
│  Streaming      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frontend       │
│  Display        │
└─────────────────┘

==================================================
3.14 MULTI-AGENT ORCHESTRATION LIFECYCLE
==================================================

When orchestration is triggered (complex tasks):

User request
       │
       ▼
┌─────────────────┐
│  Orchestrator   │
│  Service        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Task           │
│  Decomposition  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Worker         │
│  Assignment     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Sequential or  │
│  Parallel       │
│  Execution      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Approval       │
│  Chain          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Result         │
│  Aggregation    │
└─────────────────┘

Repository evidence:
- aic-platform/backend/services/orchestrator_service.py
- aic-platform/backend/models/orchestration.py

==================================================
END OF DOCUMENT
==================================================
