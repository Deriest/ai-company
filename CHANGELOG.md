# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.4.86 — 2026-08-09

### Bug Fixes

#### Provider URL Path Normalization
- **Fixed duplicate `/v1` in chat endpoints** — When user enters `https://api.aicompany.biz.id/v1` as base URL, the client now strips trailing `/v1` before constructing endpoints, preventing `.../v1/v1/chat/completions` 404 errors
- Applies to both provider test button and actual chat functionality  
- Works for any provider that uses `/v1` path (OpenAI-compatible APIs)

---

## v2.4.85 — 2026-08-09

### Bug Fixes & Activity Log Real-Time Updates

#### Critical Provider Fix
- **API key not saving when editing** — Fixed provider edit to preserve existing encrypted key; only updates when user explicitly enters new value
- **Provider test button error** — Fixed "Masked key stored" error by using backend's `/providers/{id}/test` endpoint which accesses stored encrypted key

#### Activity Log Real-Time Updates
- **Activity log now updates instantly via WebSocket** — No more 4-second polling delay for worker events
- **Correct worker names displayed** — Parses `worker.backend.started` format to show "Hugo started working" instead of task node IDs
- **Logs real-time events**: started working, completed tasks, failed errors
- Polling still handles idle/meeting status changes

#### Office Floor Layout Improvements
- **Removed project header from top** — Cleaner workspace view without distracting path/name display
- **Better worker label readability** — Increased font sizes from 7-8px to 9-10px for clear visibility
- **Project Files panel moved below Quick Stats** — Improved visual hierarchy and organization

---

## v2.4.84 — 2026-08-09

### Bug Fixes

#### Critical Provider Fix
- **API key not saving when editing** — Fixed provider edit to preserve existing encrypted key; only updates when user explicitly enters new value
- **Provider test button error** — Fixed "Masked key stored" error by using backend's `/providers/{id}/test` endpoint which accesses stored encrypted key

#### Office Floor Layout Improvements
- **Removed project header from top** — Cleaner workspace view without distracting path/name display
- **Better worker label readability** — Increased font sizes from 7-8px to 9-10px for clear visibility
- **Project Files panel moved below Quick Stats** — Improved visual hierarchy and organization

---

## v2.4.83 — 2026-08-09

### Bug Fixes & Discovery Engine Improvements

#### Critical Provider Fix
- **API key not saving when editing** — Fixed provider edit to preserve existing encrypted key

#### Office Floor & Worker Status  
- **Real-time worker status updates** — Enhanced WebSocket multi-channel subscription support

#### Discovery Engine Improvements
- **Better static fallback questions** — Enhanced domain/intent-based questions with personalized headers
- **Clearer error message** — Explicitly tells user to configure API key if discovery can't access LLM

---

## v2.4.82 — 2026-08-09

### Bug Fixes & Security Hardening

#### Critical Fixes
- **P3: executor.py** — QA worker uses `effective_repo_path` instead of `'.'`
- **P9: Sessionmaker** — Hoisted to ONE per phase to prevent session exhaustion
- **P4: websocket.py** — Disconnect_all removes socket from ALL channels (fixes leak)
- **P5: auth.py** — Brute-force lockout: 3 fails → 5min doubling each tier
- **P2: self_healing.py** — Await dispatch + audit orphaned 'investigate' tasks

#### Medium Priority Fixes
- **P6: bus.py** — Copy-on-write handler storage for lock-free publish
- **P8: main.py** — FTS5 double-init removed
- **P11: executor.py** — Ship_with_caveats surfaces caveats via events/results
- **P14: config.py** — Version fallback changed to 'unknown'
- **P15: validation.py** — URL validated with urlparse
- **P10: tool_executor.py** — Search_files regex compiled once per file
- **P12: rate_limiter.py** — Per-endpoint buckets prevent starvation
- **P13: dispatcher/engine.py** — Partial cascade vs fail-stop on failure

---

## v2.4.81 — 2026-08-09

### Worker Maximization
- **Full soul injection** — all 9 soul fields injected into every worker's context
- **Per-worker tuning policy** — WorkerTuningPolicy configured per role for all 15 workers
- **Lessons loop** — lessons_learned entries retrieved at dispatch time
- **Self-healing upgrade** — heartbeat subscribers trigger SelfHealingEngine
