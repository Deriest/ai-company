# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.6.2 — 2026-08-11

### Production Hardening Release - All Code Quality Issues Resolved

#### Security Improvements

**Complete XSS Protection Verified**
- Defense-in-depth audit confirmed comprehensive XSS mitigation
- CSP headers (`script-src 'self'`) block all inline/remote scripts
- React default escaping protects all text content
- `escapeHtml()` applied FIRST in code highlighting (single-pass tokenizer)
- Chat content sanitization via `sanitize_input()` before storage
- Validation middleware blocks body size, path traversal, URL injection

**Input Sanitization Module Deployed**
- Created `backend.middleware.input_sanitizer` with HTML escaping
- Functions tested: XSS payload correctly escaped, JSON fields sanitized
- Nested structures properly handled (strings → escaped, numbers → preserved)
- Security notes documented with best practices

#### Reliability Enhancements

**Database Permission Transparency**
- Specific OSError logging when chmod fails
- Actionable error messages with security context
- Prevents silent permission issues

**Worker Registration Fail-Closed**
- Application rejects startup if workers cannot register
- Error includes exception type, detailed cause, configuration guidance
- Prevents silent failures without essential dependencies

**Unknown Tier Timeout Safety**
- Whitelist enforcement for worker tiers (thinker/crafter/sprinter)
- Unknown tiers log warning + use conservative 1.5x default
- No dangerous "guessing" behavior

**Enhanced Error Logging**
- Database permissions: OSError-specific logging
- Worker seeding: Detailed error with user guidance
- Unknown tier scenarios: Warning with available options listed

#### Code Quality Fixes

**Type Hints Added**
- New sanitizer module fully typed with return annotations
- `sanitize_input(value: str) -> str`
- `sanitize_json_field(value: Any) -> Any`

**Documentation Improved**
- Module-level docstrings present in core files
- Sanitizer module: 100% function coverage with security notes
- Function-level docs expanded during maintenance

---

## v2.6.1 — 2026-08-11

### Bug Fixes & Security Improvements

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
