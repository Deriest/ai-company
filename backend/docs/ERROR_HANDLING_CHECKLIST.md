# Error Handling Implementation Checklist

**Project:** AIC Platform Backend Error Handling Improvements  
**Created:** 2026-07-22  
**Status:** Ready for Implementation

---

## Phase 1: Critical Security & Stability ⚠️ URGENT

### Setup (30 minutes)

- [ ] **Create error handler middleware**
  - File: `backend/middleware/error_handler.py` ✅ CREATED
  - File: `backend/middleware/__init__.py` (create if missing)
  - Test: Import in Python shell to verify no syntax errors

- [ ] **Create validation utilities**
  - File: `backend/validation.py` ✅ CREATED
  - Test: Import and run `validate_enum_value(None, TaskStatus, "test")`

- [ ] **Register middleware in main.py**
  - [ ] Add imports (after line 19)
  - [ ] Register SQLAlchemy error handler (after line 97)
  - [ ] Register ValidationError handler
  - [ ] Register generic Exception handler
  - [ ] Add trace_id middleware
  - [ ] Update rate limit handler with Retry-After
  - Test: Start server, verify no import errors

### Authorization Fixes ⚠️ CRITICAL (1 hour)

- [ ] **Fix projects.py**
  - [ ] Line 66-76: Add `Project.owner_id == user.id` to get_project query
  - [ ] Line 79-100: Add ownership check to get_project_tasks
  - [ ] Line 103-112: Add ownership check to get_milestones (if exists)
  - Test: Try to access another user's project → expect 404

- [ ] **Fix tasks.py**
  - [ ] Line 136-153: Add project ownership check to dispatch_task
  - [ ] Add project ownership check to cancel_task (if exists)
  - Test: Try to dispatch another user's task → expect 404

- [ ] **Fix conversations.py**
  - [ ] Line 222-244: Add conversation ownership check to get_messages
  - [ ] Verify all other endpoints already check `Conversation.user_id == user.id`
  - Test: Try to access another user's messages → expect 404

### Input Validation (1.5 hours)

- [ ] **Fix tasks.py**
  - [ ] Add import: `from backend.validation import validate_enum_value`
  - [ ] Add import: `from storage.models import TaskStatus, TaskType`
  - [ ] Line 43: Add `validate_enum_value(status, TaskStatus, "status")`
  - [ ] Line 49: Add project existence check if project_id provided
  - Test: GET `/api/tasks?status=invalid` → expect 400

- [ ] **Fix conversations.py**
  - [ ] Add import: `from backend.validation import BatchAction`
  - [ ] Add import: `from pydantic import validator`
  - [ ] Line 34-36: Change BatchRequest.action to `BatchAction` enum
  - [ ] Line 39-41: Add validator to MessageSend.content (max 50KB)
  - [ ] Line 82-89: Remove manual action validation (now handled by enum)
  - [ ] Update batch logic to use `BatchAction.DELETE`, etc.
  - Test: POST batch with action="invalid" → expect 422
  - Test: POST message with 51KB content → expect 422

- [ ] **Fix approvals.py**
  - [ ] Add import: `from backend.validation import ApprovalDecisionType`
  - [ ] Line 15-17: Change ApprovalDecision.decision to enum
  - [ ] Line 86: Update to use `ApprovalDecisionType.APPROVED`
  - Test: POST decision with decision="maybe" → expect 422

### Database Error Handling (30 minutes)

- [ ] **Verify middleware is registered**
  - [ ] Check main.py has `app.add_exception_handler(SQLAlchemyError, ...)`
  - [ ] Test: Stop database, make API call → expect 503 with clean message
  - [ ] Test: Verify no stack traces in response

- [ ] **Test constraint violations**
  - [ ] Test: Create duplicate username → expect 409
  - [ ] Test: Reference non-existent foreign key → expect 400
  - [ ] Verify trace_id in all error responses

### Phase 1 Testing (1 hour)

- [ ] **Manual testing**
  - [ ] Restart server, verify no errors
  - [ ] Test all authorization fixes
  - [ ] Test all validation fixes
  - [ ] Test database error scenarios
  - [ ] Verify trace_id in all responses

- [ ] **Automated tests**
  - [ ] Run existing test suite
  - [ ] All tests pass or update tests for new behavior

---

## Phase 2: Error Quality Improvements (4 hours)

### LLM Provider Error Classification (1 hour)

- [ ] **Fix llm.py test_provider**
  - [ ] Add import: `import httpx`
  - [ ] Line 215-249: Replace test_provider implementation
  - [ ] Catch `httpx.TimeoutException` specifically
  - [ ] Catch `httpx.ConnectError` specifically
  - [ ] Catch `httpx.HTTPStatusError` and classify 401/403
  - [ ] Generic catch-all with error type
  - Test: Mock different error types, verify correct codes returned

- [ ] **Fix llm.py fetch_models**
  - [ ] Line 252-283: Apply same error classification
  - [ ] Return structured errors instead of raising HTTPException
  - Test: Same as test_provider

### Background Task Error Handling (1 hour)

- [ ] **Fix conversations.py background task**
  - [ ] Line 329-348: Add error recovery in _dispatch_created_task
  - [ ] On exception, update task.status = "failed"
  - [ ] Set task.error_message = str(e)[:500]
  - [ ] Wrap update in try-except to avoid double-failure
  - Test: Mock executor failure, verify task status updated

- [ ] **Fix tasks.py background task**
  - [ ] Line 175-185: Same pattern as conversations
  - Test: Same as above

### Standardize Error Messages (1 hour)

- [ ] **Review all HTTPException calls**
  - [ ] conversations.py line 89: Change "Invalid action" to structured error
  - [ ] approvals.py line 84: Change "Approval already {status}" format
  - [ ] Add error codes where missing
  - [ ] Ensure all errors have consistent format

- [ ] **Update 404 messages**
  - [ ] Ensure all say "Resource not found" or similar
  - [ ] Remove "or access denied" (security through obscurity)
  - [ ] Consistent capitalization

### Add Input Length Validation (30 minutes)

- [ ] **conversations.py MessageSend**
  - [ ] Already done in Phase 1 validation section
  - [ ] Verify 50KB limit
  - [ ] Verify empty string rejection

- [ ] **Check other text inputs**
  - [ ] projects.py: description length limit?
  - [ ] tasks.py: description length limit?
  - [ ] Add as needed

### Request Tracing (30 minutes)

- [ ] **Already implemented in middleware**
  - [ ] Verify trace_id middleware registered in main.py
  - [ ] Test: Make request without X-Trace-ID → gets generated
  - [ ] Test: Make request with X-Trace-ID → preserved
  - [ ] Verify X-Trace-ID in response headers
  - [ ] Verify trace_id in error responses

### Phase 2 Testing (30 minutes)

- [ ] Test all error scenarios return structured responses
- [ ] Test trace_id appears in logs
- [ ] Verify background tasks update status on failure
- [ ] Verify LLM provider errors are classified

---

## Phase 3: Polish & Production Readiness (2 hours)

### WebSocket Improvements (30 minutes)

- [ ] **Fix websocket.py**
  - [ ] Line 115-119: Wrap json.loads in try-except
  - [ ] Send error message on JSONDecodeError
  - [ ] Don't close connection, just send error and continue
  - Test: Send invalid JSON → expect error response, connection stays open

- [ ] **Add connection limits (optional)**
  - [ ] Track connections per user
  - [ ] Reject if user has >10 connections?
  - [ ] Add configuration for limit

### Console Safety (30 minutes)

- [ ] **Fix console.py**
  - [ ] Line 32-58: Wrap LOG_FILE.read_text() in try-except
  - [ ] Add file size check before reading
  - [ ] Limit to 100MB
  - [ ] Handle PermissionError separately
  - Test: Create large log file → expect error
  - Test: Remove read permissions → expect 403

### HTTP Status Codes (15 minutes)

- [ ] **Add 201 to create endpoints**
  - [ ] auth.py line 41: `@router.post("/register", status_code=201)`
  - [ ] projects.py line 44: `@router.post("", status_code=201)`
  - [ ] tasks.py line 72: `@router.post("", status_code=201)`
  - [ ] conversations.py line 114: `@router.post("", status_code=201)`
  - [ ] users.py line 48: `@router.post("", status_code=201)`
  - [ ] llm.py line 71: `@router.post("/providers", status_code=201)`
  - Test: Verify responses return 201, not 200

### Documentation (45 minutes)

- [ ] **API documentation**
  - [ ] Document error response format
  - [ ] List all error codes
  - [ ] Show example error responses
  - [ ] Document trace_id usage

- [ ] **Developer guide**
  - [ ] How to add new validation
  - [ ] How to use validation helpers
  - [ ] Error handling patterns
  - [ ] When to use which status code

- [ ] **Update OpenAPI/Swagger**
  - [ ] Add error response schemas
  - [ ] Document status codes per endpoint

---

## Testing & Validation (4 hours)

### Unit Tests

- [ ] **Test validation helpers**
  - [ ] test_validate_enum_value with valid/invalid values
  - [ ] test_validate_positive_integer with edge cases
  - [ ] test_validate_resource_exists
  - [ ] test_validate_resource_ownership
  - [ ] test_validate_string_length

- [ ] **Test authorization**
  - [ ] test_get_project_unauthorized
  - [ ] test_get_project_tasks_unauthorized
  - [ ] test_dispatch_task_unauthorized
  - [ ] test_get_messages_unauthorized

- [ ] **Test input validation**
  - [ ] test_invalid_enum_values
  - [ ] test_oversized_content
  - [ ] test_empty_strings
  - [ ] test_out_of_range_limits

### Integration Tests

- [ ] **End-to-end error scenarios**
  - [ ] Create project → try to access as different user → 404
  - [ ] Create task → dispatch as different user → 404
  - [ ] Send message with 51KB → 422
  - [ ] Invalid enum in query → 400
  - [ ] Database down → 503

- [ ] **Background task testing**
  - [ ] Mock executor failure → verify task.status = "failed"
  - [ ] Check task.error_message populated

### Load Testing

- [ ] **Performance validation**
  - [ ] Measure authorization check overhead
  - [ ] Measure validation overhead
  - [ ] Ensure <5ms added latency
  - [ ] Verify no memory leaks in error handling

### Manual QA

- [ ] Test with Postman/curl
- [ ] Verify error messages are user-friendly
- [ ] Check no stack traces leak
- [ ] Verify trace_id in all errors
- [ ] Test rate limiting with Retry-After

---

## Deployment

### Pre-Deployment

- [ ] **Code review**
  - [ ] Review all changes
  - [ ] Security review of authorization changes
  - [ ] Performance review

- [ ] **Staging deployment**
  - [ ] Deploy to staging
  - [ ] Run full test suite
  - [ ] Manual QA
  - [ ] Monitor for 24 hours

### Production Deployment

- [ ] **Prepare rollback**
  - [ ] Tag current production version
  - [ ] Document rollback procedure
  - [ ] Test rollback in staging

- [ ] **Deploy**
  - [ ] Deploy during low-traffic window
  - [ ] Canary deploy to 10% traffic first
  - [ ] Monitor error rates
  - [ ] Gradually increase to 100%

- [ ] **Post-deployment monitoring**
  - [ ] Monitor error rates by code
  - [ ] Check authorization denial rates
  - [ ] Verify trace_id in logs
  - [ ] Monitor performance metrics
  - [ ] Check for any regressions

### Post-Deployment

- [ ] **Update documentation**
  - [ ] Publish API docs with error codes
  - [ ] Update developer guide
  - [ ] Create runbook for troubleshooting

- [ ] **Team training**
  - [ ] Train support on new error codes
  - [ ] Train devs on validation patterns
  - [ ] Demo trace_id usage for debugging

---

## Rollback Triggers

Rollback immediately if:
- [ ] Authorization checks cause >1% false negatives
- [ ] Error rate increases >50%
- [ ] Response times increase >20%
- [ ] Database errors not handled properly
- [ ] Any data leak detected

---

## Success Criteria

- [ ] ✅ Zero authorization bypasses
- [ ] ✅ All database errors return clean messages
- [ ] ✅ All errors include trace_id
- [ ] ✅ Invalid inputs return 400/422 with details
- [ ] ✅ External service errors classified
- [ ] ✅ Background tasks update on failure
- [ ] ✅ No performance degradation >5%
- [ ] ✅ Test coverage >85%
- [ ] ✅ Documentation complete

---

## Sign-off

- [ ] Developer: Implementation complete
- [ ] QA: Testing complete
- [ ] Security: Authorization reviewed
- [ ] DevOps: Monitoring configured
- [ ] Product: Error messages reviewed

---

**Estimated Total Time:** 16-17 hours  
**Recommended Schedule:** 3 days with testing  
**Risk Level:** Medium (critical changes, but well-scoped)  
**Priority:** High (security issues present)
