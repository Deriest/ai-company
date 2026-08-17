# 19 — IMPLEMENTATION WORK BREAKDOWN

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
19.1 WORK PACKAGE OVERVIEW
==================================================

10 Work Packages (WP-01 through WP-10)
Total estimated time: 12-15 hours
Critical path: WP-01 → WP-02 → WP-03 → WP-04 → WP-05 → WP-06 → WP-07 → WP-08 → WP-09 → WP-10

==================================================
19.2 WORK PACKAGES
==================================================

--------------------------------------------------
WP-01: Conversation Intent Gateway
--------------------------------------------------

Title: Conversation Intent Gateway

Objective: Add intent detection to the chat stream endpoint without changing behavior.

Repository files involved:
- backend/api/routes/core.py (MODIFY)

Dependencies: None

Expected code changes:
- Import ConversationEngine
- Import _detect_intent function
- Add intent detection before ChatService call
- Log intent for debugging
- No behavior change

Expected tests:
- Test intent detection is called
- Test intent is logged
- Test no behavior change

Success criteria:
- Intent detection runs before every chat request
- Intent is logged
- Chat behavior unchanged
- All existing tests pass

Rollback criteria:
- Intent detection fails
- Performance degradation > 500ms
- Existing tests fail

Estimated implementation time: 1 hour

Risk level: LOW

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: Intent detection added

--------------------------------------------------
WP-02: Conversation Routing
--------------------------------------------------

Title: Conversation Routing

Objective: Route requests based on detected intent.

Repository files involved:
- backend/api/routes/core.py (MODIFY)

Dependencies: WP-01

Expected code changes:
- Add routing logic based on intent
- If intent is chat/question: Call ChatService.chat_stream()
- If intent is task_request: Call ConversationEngine._handle_task_request()
- If intent is task_confirm: Call ConversationEngine._handle_task_confirm()
- Add fallback for unknown intents

Expected tests:
- Test chat intent routes to ChatService
- Test task_request intent routes to ConversationEngine
- Test task_confirm intent routes to ConversationEngine
- Test unknown intent falls back to ChatService

Success criteria:
- Requests are routed based on intent
- Chat intent preserves streaming
- Task intents are handled by ConversationEngine
- All existing tests pass

Rollback criteria:
- Routing logic fails
- Streaming breaks
- Existing tests fail

Estimated implementation time: 2 hours

Risk level: MEDIUM

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: Request routing added

--------------------------------------------------
WP-03: Task Request Pipeline
--------------------------------------------------

Title: Task Request Pipeline

Objective: Handle task_request intent with clarification.

Repository files involved:
- backend/api/routes/core.py (MODIFY)
- conversation/engine.py (READ ONLY)

Dependencies: WP-02

Expected code changes:
- Call ConversationEngine._handle_task_request()
- Return clarification questions
- Handle LLMUnavailableError
- Handle LLMInferenceError

Expected tests:
- Test task request returns clarification
- Test LLM errors are handled
- Test response format is correct

Success criteria:
- Task requests return clarification questions
- LLM errors are handled gracefully
- Response includes intent and metadata

Rollback criteria:
- Task request fails
- Clarification not returned
- LLM errors crash

Estimated implementation time: 2 hours

Risk level: MEDIUM

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: Response includes intent and metadata
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: Task request handling added

--------------------------------------------------
WP-04: Task Confirmation Pipeline
--------------------------------------------------

Title: Task Confirmation Pipeline

Objective: Handle task_confirm intent with task creation.

Repository files involved:
- backend/api/routes/core.py (MODIFY)
- conversation/engine.py (READ ONLY)

Dependencies: WP-03

Expected code changes:
- Call ConversationEngine._handle_task_confirm()
- Create Task in database
- Return task creation confirmation
- Handle errors

Expected tests:
- Test task confirmation creates task
- Test task_id is returned
- Test errors are handled

Success criteria:
- Task confirmation creates task in database
- Task ID is returned in response
- Errors are handled gracefully

Rollback criteria:
- Task creation fails
- Task ID not returned
- Database errors

Estimated implementation time: 2 hours

Risk level: MEDIUM

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: Response includes task_id
Internal API changes: None
Database impact: Task creation
Frontend impact: None
Backend impact: Task creation added

--------------------------------------------------
WP-05: Runtime Dispatch Integration
--------------------------------------------------

Title: Runtime Dispatch Integration

Objective: Connect task creation to Runtime Executor.

Repository files involved:
- backend/api/routes/core.py (MODIFY)
- runtime/executor.py (READ ONLY)

Dependencies: WP-04

Expected code changes:
- Import Runtime Executor
- Call execute_task() when task is created
- Handle execution errors
- Return execution status

Expected tests:
- Test task dispatch calls execute_task()
- Test execution errors are handled
- Test execution status is returned

Success criteria:
- Created tasks are dispatched to Runtime Executor
- Execution errors are handled
- Execution status is returned

Rollback criteria:
- Dispatch fails
- Execution errors crash
- Status not returned

Estimated implementation time: 1 hour

Risk level: LOW

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: Response includes execution status
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: Task dispatch added

--------------------------------------------------
WP-06: Background Task Execution
--------------------------------------------------

Title: Background Task Execution

Objective: Execute tasks in background to avoid blocking chat.

Repository files involved:
- backend/api/routes/core.py (MODIFY)

Dependencies: WP-05

Expected code changes:
- Import BackgroundTasks
- Add background task dispatch
- Call _dispatch_created_task() in background
- Handle background task errors

Expected tests:
- Test background task is dispatched
- Test background task errors are handled
- Test chat is not blocked

Success criteria:
- Tasks execute in background
- Chat is not blocked
- Background errors are logged

Rollback criteria:
- Background task fails
- Chat is blocked
- Errors not logged

Estimated implementation time: 1 hour

Risk level: LOW

Files modified: 1 (core.py)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: Background task dispatch added

--------------------------------------------------
WP-07: Frontend Event & Metadata Handling
--------------------------------------------------

Title: Frontend Event & Metadata Handling

Objective: Parse intent and metadata from response.

Repository files involved:
- src/renderer/src/lib/api/chat.ts (MODIFY)

Dependencies: WP-03

Expected code changes:
- Parse intent field in done event
- Parse metadata field in done event
- Display task creation feedback
- Display clarification questions

Expected tests:
- Test intent parsing
- Test metadata parsing
- Test task feedback display
- Test clarification display

Success criteria:
- Intent is parsed from response
- Metadata is parsed from response
- Task feedback is displayed
- Clarification questions are displayed

Rollback criteria:
- Parsing fails
- Feedback not displayed
- Clarification not displayed

Estimated implementation time: 2 hours

Risk level: LOW

Files modified: 1 (chat.ts)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: Intent and metadata handling
Backend impact: None

--------------------------------------------------
WP-08: Streaming Compatibility
--------------------------------------------------

Title: Streaming Compatibility

Objective: Ensure streaming works correctly with all intents.

Repository files involved:
- backend/api/routes/core.py (MODIFY)
- src/renderer/src/lib/api/chat.ts (MODIFY)

Dependencies: WP-02, WP-07

Expected code changes:
- Test streaming with chat intent
- Test streaming with task intent
- Test streaming with question intent
- Fix any streaming issues

Expected tests:
- Test streaming with chat intent
- Test streaming with task intent
- Test streaming with question intent
- Test streaming error handling

Success criteria:
- Streaming works with all intents
- No streaming regression
- Error handling works

Rollback criteria:
- Streaming breaks
- Regression detected
- Error handling fails

Estimated implementation time: 1 hour

Risk level: MEDIUM

Files modified: 2 (core.py, chat.ts)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: Streaming compatibility
Backend impact: Streaming compatibility

--------------------------------------------------
WP-09: Regression Tests
--------------------------------------------------

Title: Regression Tests

Objective: Ensure all existing tests pass.

Repository files involved:
- tests/ (READ ONLY)

Dependencies: WP-08

Expected code changes:
- Run all existing tests
- Fix any failures
- Add new tests for integration

Expected tests:
- All existing tests pass
- New integration tests pass

Success criteria:
- All existing tests pass
- New integration tests pass
- No regression

Rollback criteria:
- Existing tests fail
- New tests fail
- Regression detected

Estimated implementation time: 2 hours

Risk level: LOW

Files modified: None
Files untouched: All
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: None

--------------------------------------------------
WP-10: Legacy Route Deprecation
--------------------------------------------------

Title: Legacy Route Deprecation

Objective: Mark legacy routes as deprecated.

Repository files involved:
- backend/routes/conversations.py (MODIFY)

Dependencies: WP-09

Expected code changes:
- Add deprecation comments
- No functional changes

Expected tests:
- All existing tests pass

Success criteria:
- Legacy routes are marked as deprecated
- No functional changes
- All tests pass

Rollback criteria:
- Tests fail
- Functional changes detected

Estimated implementation time: 0.5 hours

Risk level: NONE

Files modified: 1 (conversations.py)
Files untouched: All others
Public API changes: None
Internal API changes: None
Database impact: None
Frontend impact: None
Backend impact: None

==================================================
19.3 IMPLEMENTATION ORDER
==================================================

ORDER: WP-01 → WP-02 → WP-03 → WP-04 → WP-05 → WP-06 → WP-07 → WP-08 → WP-09 → WP-10

REASON FOR ORDER:

1. WP-01 (Intent Gateway): Foundation for all other work
2. WP-02 (Routing): Depends on intent detection
3. WP-03 (Task Request): Depends on routing
4. WP-04 (Task Confirm): Depends on routing
5. WP-05 (Runtime Dispatch): Depends on task creation
6. WP-06 (Background Execution): Depends on dispatch
7. WP-07 (Frontend): Depends on backend changes
8. WP-08 (Streaming): Depends on routing and frontend
9. WP-09 (Regression): Depends on all changes
10. WP-10 (Deprecation): Final cleanup

MINIMIZES REGRESSION RISK BECAUSE:
- Each WP builds on previous
- Each WP is independently testable
- Each WP can be rolled back
- No WP requires unfinished work

==================================================
19.4 IMPLEMENTATION TIMELINE
==================================================

DAY 1: WP-01, WP-02 (3 hours)
DAY 2: WP-03, WP-04 (4 hours)
DAY 3: WP-05, WP-06 (2 hours)
DAY 4: WP-07, WP-08 (3 hours)
DAY 5: WP-09, WP-10 (2.5 hours)

TOTAL: 14.5 hours (5 days)

==================================================
19.5 CRITICAL PATH
==================================================

WP-01 → WP-02 → WP-03 → WP-04 → WP-05 → WP-06 → WP-07 → WP-08 → WP-09 → WP-10

CRITICAL PATH TIME: 14.5 hours

==================================================
19.6 PARALLELIZABLE WORK
==================================================

PARALLEL GROUP 1: WP-01, WP-02 (can be done together)
PARALLEL GROUP 2: WP-03, WP-04 (can be done together)
PARALLEL GROUP 3: WP-05, WP-06 (can be done together)
PARALLEL GROUP 4: WP-07, WP-08 (can be done together)
PARALLEL GROUP 5: WP-09, WP-10 (can be done together)

PARALLEL TIME: 7.25 hours (if 2 developers)

==================================================
19.7 MERGE STRATEGY
==================================================

MERGE ORDER:
1. WP-01 + WP-02: Merge as single PR
2. WP-03 + WP-04: Merge as single PR
3. WP-05 + WP-06: Merge as single PR
4. WP-07 + WP-08: Merge as single PR
5. WP-09 + WP-10: Merge as single PR

MERGE CRITERIA:
- All tests pass
- Code review approved
- No regression

==================================================
19.8 ROLLBACK STRATEGY
==================================================

ROLLBACK LEVELS:

LEVEL 1: Individual WP rollback
- Revert specific WP changes
- Keep other WPs

LEVEL 2: Group rollback
- Revert group of WPs
- Keep previous groups

LEVEL 3: Full rollback
- Revert all changes
- Return to original state

ROLLBACK PROCEDURE:
1. Identify failing WP
2. Revert WP changes
3. Run tests
4. If tests pass, continue
5. If tests fail, revert group

==================================================
19.9 RELEASE STRATEGY
==================================================

RELEASE PHASES:

PHASE 1: Development
- Implement WP-01 through WP-06
- Test backend changes
- No frontend changes

PHASE 2: Frontend
- Implement WP-07 through WP-08
- Test frontend changes
- Test integration

PHASE 3: Validation
- Implement WP-09 through WP-10
- Full regression testing
- Performance testing

PHASE 4: Release
- Merge all PRs
- Deploy to staging
- User acceptance testing
- Deploy to production

==================================================
END OF DOCUMENT
==================================================
