# 17 — INTEGRATION IMPLEMENTATION SPECIFICATION

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
17.1 FILES THAT MUST CHANGE
==================================================

BACKEND FILES:

1. backend/api/routes/core.py
2. backend/services/chat_service.py
3. backend/routes/conversations.py (minor cleanup)

FRONTEND FILES:

4. src/renderer/src/lib/api/chat.ts

NO OTHER FILES NEED CHANGES.

==================================================
17.2 FILE-BY-FILE SPECIFICATION
==================================================

--------------------------------------------------
FILE 1: backend/api/routes/core.py
--------------------------------------------------

Current Responsibility:
- Handle /chat/stream requests
- Call ChatService.chat_stream() directly
- Simple passthrough to LLM

Future Responsibility:
- Handle /chat/stream requests
- Call ConversationEngine.process_message()
- Intent detection, task creation, workflow execution
- Stream response to frontend

Reason for Change:
- This is the PRIMARY integration point
- Currently bypasses ConversationEngine
- Must connect to existing ConversationEngine

Estimated Complexity: MEDIUM

Changes Required:
- Import ConversationEngine
- Import BackgroundTasks dependency
- Import Conversation model
- Replace ChatService.chat_stream() call with ConversationEngine.process_message()
- Add background task dispatch for created tasks
- Update response format to include intent and metadata

--------------------------------------------------
FILE 2: backend/services/chat_service.py
--------------------------------------------------

Current Responsibility:
- Provide chat_stream() and chat_completion() methods
- Direct LLM passthrough
- Message storage
- Artifact extraction

Future Responsibility:
- KEEP existing methods for backward compatibility
- Add new method: chat_with_engine() that calls ConversationEngine
- Provide fallback when ConversationEngine fails

Reason for Change:
- ConversationEngine may fail (LLM unavailable, etc.)
- Need graceful fallback to simple passthrough
- Preserve existing functionality

Estimated Complexity: LOW

Changes Required:
- Add chat_with_engine() method
- Keep existing chat_stream() and chat_completion() for fallback
- Add error handling for ConversationEngine failures

--------------------------------------------------
FILE 3: backend/routes/conversations.py
--------------------------------------------------

Current Responsibility:
- Legacy chat endpoints
- Full ConversationEngine integration
- Task dispatch

Future Responsibility:
- Deprecate (mark as legacy)
- Keep for backward compatibility
- No functional changes

Reason for Change:
- This file ALREADY has the integration
- Frontend doesn't use it
- Keep as reference implementation

Estimated Complexity: NONE

Changes Required:
- Add deprecation comments
- No functional changes

--------------------------------------------------
FILE 4: src/renderer/src/lib/api/chat.ts
--------------------------------------------------

Current Responsibility:
- Call /chat/stream endpoint
- Parse SSE stream
- Handle chunks, done, error events

Future Responsibility:
- SAME responsibility
- Parse additional metadata from response
- Handle intent field in done event
- Display task creation feedback

Reason for Change:
- Response format will include intent and metadata
- Frontend needs to handle task creation feedback
- User should see "Task created" messages

Estimated Complexity: LOW

Changes Required:
- Update done event handler to parse intent and metadata
- Add task creation feedback display
- Keep existing chunk handling

==================================================
17.3 APIs THAT REMAIN UNCHANGED
==================================================

- POST /chat (non-streaming) — Keep as-is
- POST /chat/cancel — Keep as-is
- POST /chat/regenerate — Keep as-is
- GET /conversations — Keep as-is
- POST /conversations — Keep as-is
- GET /conversations/{id}/messages — Keep as-is
- POST /api/conversations/{id}/stream — Keep as-is (legacy)
- All other API endpoints — Keep as-is

==================================================
17.4 APIs THAT BECOME WRAPPERS
==================================================

NONE

The /chat/stream endpoint will be MODIFIED, not wrapped.
The ConversationEngine will be called DIRECTLY from the route handler.

==================================================
17.5 APIs THAT BECOME DEPRECATED
==================================================

- POST /api/conversations/{id}/stream — Mark as deprecated
- POST /api/conversations/{id}/messages/stream — Mark as deprecated

These legacy endpoints will continue to work but will be marked as deprecated.

==================================================
17.6 MIGRATION ORDER
==================================================

STEP 1: Add ConversationEngine import to core.py
- Import ConversationEngine, LLMUnavailableError, LLMInferenceError
- Import BackgroundTasks dependency
- Import Conversation model

STEP 2: Modify chat_stream_endpoint() in core.py
- Load Conversation from database
- Create ConversationEngine instance
- Call process_message()
- Handle LLMUnavailableError (fallback to simple passthrough)
- Handle LLMInferenceError (fallback to simple passthrough)
- Stream response with intent and metadata

STEP 3: Add background task dispatch
- If task_id in response metadata
- Call _dispatch_created_task() in background
- Execute task through Runtime Executor

STEP 4: Update frontend response parsing
- Parse intent field in done event
- Parse metadata field in done event
- Display task creation feedback

STEP 5: Add deprecation comments to legacy routes
- Mark /api/conversations/{id}/stream as deprecated
- Mark /api/conversations/{id}/messages/stream as deprecated

==================================================
17.7 ROLLBACK STRATEGY
==================================================

ROLLBACK PLAN:

If integration fails:
1. Revert core.py to simple passthrough
2. Frontend continues to work (no changes required)
3. Legacy routes still available as fallback

ROLLBACK TRIGGERS:
- ConversationEngine fails consistently
- Performance degradation > 2x
- Task creation fails
- Runtime Executor fails

ROLLBACK PROCEDURE:
1. Comment out ConversationEngine code in core.py
2. Restore ChatService.chat_stream() call
3. Restart backend

==================================================
17.8 COMPATIBILITY RISKS
==================================================

RISK 1: ConversationEngine requires LLM
- Impact: HIGH
- Mitigation: Fallback to simple passthrough when LLM unavailable
- Evidence: conversation/engine.py:171 — _detect_intent_llm() calls LLM

RISK 2: ConversationEngine requires database session
- Impact: LOW
- Mitigation: Already available in route handler
- Evidence: core.py:837 — db: AsyncSession = Depends(get_db)

RISK 3: ConversationEngine creates tasks
- Impact: MEDIUM
- Mitigation: Background task dispatch already implemented in legacy route
- Evidence: conversations.py:348 — _dispatch_created_task()

RISK 4: Response format changes
- Impact: LOW
- Mitigation: Frontend already handles chunk, done, error events
- Evidence: chat.ts:52-74 — Event parsing

RISK 5: Performance degradation
- Impact: MEDIUM
- Mitigation: ConversationEngine adds intent detection + task creation
- Expected: +100-200ms per request
- Acceptable for desktop application

RISK 6: Task creation side effects
- Impact: LOW
- Mitigation: Tasks only created when user confirms
- Evidence: conversation/engine.py:310 — _handle_task_request()

==================================================
17.9 IMPLEMENTATION SEQUENCE
==================================================

PHASE 1: Backend Integration (core.py)
- Import ConversationEngine
- Modify chat_stream_endpoint()
- Add fallback logic
- Add background task dispatch

PHASE 2: Frontend Enhancement (chat.ts)
- Parse intent and metadata
- Display task creation feedback

PHASE 3: Legacy Cleanup (conversations.py)
- Add deprecation comments
- No functional changes

PHASE 4: Testing
- Test chat with ConversationEngine
- Test fallback to simple passthrough
- Test task creation
- Test background dispatch
- Test frontend feedback

PHASE 5: Validation
- Verify all existing tests pass
- Verify new integration works
- Verify fallback works
- Verify task creation works

==================================================
17.10 ESTIMATED EFFORT
==================================================

BACKEND CHANGES:
- core.py: 2-3 hours
- chat_service.py: 1 hour
- conversations.py: 0.5 hours (comments only)

FRONTEND CHANGES:
- chat.ts: 1-2 hours

TESTING:
- Unit tests: 2 hours
- Integration tests: 2 hours
- Manual testing: 1 hour

TOTAL: 9.5-11.5 hours

==================================================
17.11 SUCCESS CRITERIA
==================================================

1. Chat uses ConversationEngine for intent detection
2. Task requests trigger clarification
3. Confirmed tasks create Task in database
4. Tasks execute through Runtime Executor
5. Frontend displays task creation feedback
6. Fallback works when ConversationEngine fails
7. All existing tests pass
8. No performance regression > 2x

==================================================
END OF DOCUMENT
==================================================
