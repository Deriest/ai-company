# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.6.1 — 2026-08-11

### Security & Reliability Improvements

#### Critical Fixes

**Database Permission Security Hardening**
- `session.py`: Database permission failures now logged with specific OSError details and actionable guidance instead of generic warnings
- Added `OSError` handler with clear message about security implications
- Provides user with specific error type and recommended remediation steps

**Input Sanitization (XSS Prevention)**
- Created new `backend.middleware.input_sanitizer` module with centralized HTML escaping
- Integrated `sanitize_input()` into chat routes to prevent XSS attacks from user content
- Messages stored as escaped HTML (`&lt;script&gt;`) to safely render text without execution
- Applies `html.escape()` before database storage for all user inputs

**Worker Registration Fail-Closed**
- Changed worker seeding from "warning-only" to fail-closed behavior
- Application now rejects startup if critical worker registration fails
- Error messages include exception type, detailed cause, and configuration guidance
- Prevents silent failure where app runs without essential workers

**Unknown Tier Timeout Safety**
- Implemented tier validation in adaptive timeout calculation
- Unknown worker tiers now log warning with known tier list and use conservative 1.5x default
- Replaces dangerous "2.0x guess" with explicit safe handling
- Prevents premature timeouts or performance degradation on misconfiguration

#### Code Quality Improvements

**Enhanced Error Logging**
- Database permission errors: Specific `OSError` logging vs generic exceptions
- Worker seeding failures: Detailed error with exception type and user guidance
- Unknown tier scenarios: Warning logs with available options listed
- All critical paths now provide actionable error information

**Fail-Safe Defaults**
- Worker tier multipliers: Only known tiers allowed, unknown tiers get conservative fallback
- Configuration validation: Clear errors when critical settings missing
- Input sanitization: Gracefully handles empty/invalid inputs

---

## v2.4.87 — 2026-08-09

### Bug Fixes & Improvements

#### Provider Configuration & Testing
- **Fixed provider client URL handling** - reverted problematic `/v1` stripping logic; httpx handles URL merge correctly natively
- **Provider API key preservation** - editing providers now correctly preserves existing encrypted key; only updates when user enters new value
- **Provider test response format fix** - supports both camelCase (`latencyMs`) and snake_case (`latency_ms`) backend responses
- **Provider test button working** - uses backend's `/providers/{id}/test` endpoint to access stored encrypted keys instead of masked client-side values

#### Activity Log Real-Time Updates
- **WebSocket-powered instant logging** - Activity log updates immediately on worker events (started/completed/failed) via `worker.backend.started`, etc. events
- **Correct worker name mapping** - Parses event type format to display "Hugo started working" instead of task node IDs
- **Polling fallback** - 4s interval handles idle/meeting status transitions as backup

#### Office Floor UI Improvements
- **Readable worker labels** - Increased font sizes from 7-8px to 9-10px for clear visibility of all 15 workers
- **Cleaner layout** - Removed redundant project header from top of office view
- **Better hierarchy** - Project Files panel positioned below Quick Stats bar

---

## v2.4.86 — 2026-08-09

### Bug Fixes

#### Provider URL Path Normalization
- Attempted fix for duplicate `/v1` paths in chat endpoints (reverted due to httpx compatibility issues)

---

## v2.4.85 — 2026-08-09

### Bug Fixes & Activity Log Real-Time Updates

#### Critical Provider Fix
- **API key not saving when editing** - Fixed provider edit to preserve existing encrypted key
- **Provider test button error** - Fixed "Masked key stored" error using backend endpoint

#### Activity Log Real-Time Updates
- **Activity log updates instantly via WebSocket** - No more 4-second delay for worker events
- **Correct worker names displayed** - Shows "Hugo" not node IDs

#### Office Floor Layout Improvements
- **Removed project header from top** - Cleaner workspace view
- **Better worker label readability** - Increased fonts to 9-10px
- **Project Files panel below Quick Stats** - Improved visual hierarchy

---

## v2.4.84 — 2026-08-09

### Bug Fixes

#### Critical Provider Fix
- **API key not saving when editing** - Fixed provider edit to preserve existing encrypted key

#### Office Floor Layout Improvements
- **Removed project header from top** - Cleaner workspace view
- **Better worker label readability** - Increased fonts to 9-10px
- **Project Files panel moved below Quick Stats** - Improved visual hierarchy

---

## v2.4.83 — 2026-08-09

### Bug Fixes & Discovery Engine Improvements

#### Critical Provider Fix
- **API key not saving when editing** - Fixed provider edit to preserve existing encrypted key

#### Office Floor & Worker Status  
- **Real-time worker status updates** - Enhanced WebSocket multi-channel subscription support

#### Discovery Engine Improvements
- **Better static fallback questions** - Enhanced domain/intent-based questions with personalized headers
- **Clearer error message** - Explicitly tells user to configure API key if discovery can't access LLM

---

## v2.4.82 — 2026-08-09

### Bug Fixes & Security Hardening

#### Critical Fixes
- **P3-P15 comprehensive security hardening** - Including SQLite lock retry, SSRF guards, path traversal protection

---

## v2.4.81 — 2026-08-09

### Worker Maximization
- **Full soul injection** - all 9 soul fields injected into every worker's context
- **Per-worker tuning policy** - WorkerTuningPolicy configured per role for all 15 workers
- **Lessons loop** - lessons_learned entries retrieved at dispatch time
- **Self-healing upgrade** - heartbeat subscribers trigger SelfHealingEngine
## v2.4.88 — 2026-08-09

### Bug Fixes & Real-Time Improvements

#### Office Floor Real-Time Updates
- **Activity Log now updates INSTANTLY** — No more waiting for 4s polling cycles
- Added WebSocket broadcasts from chat task execution (AgentRunner path)
- Broadcasts `worker.backend.started/completed/failed` events to frontend
- Office Floor worker status updates immediately when tasks begin/end
- Works for ALL task paths: chat → AgentRunner AND executor → FSM

#### Related Fixes Included:
- Discovery session marker clearing (prevents re-triggering on follow-up chat)
- Worker name display improvements (clear, readable fonts)

---
