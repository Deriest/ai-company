# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.4.83 — 2026-08-09

### Bug Fixes

#### Critical Provider Fix
- **API key not saving when editing** — Fixed provider edit to preserve existing encrypted key; only updates when user explicitly enters new value

#### Office Floor & Worker Status  
- **Real-time worker status updates** — Enhanced WebSocket multi-channel subscription support for live office floor updates

#### Discovery Engine Improvements
- **Better static fallback questions** — Enhanced domain/intent-based questions with personalized headers (e.g., "For fixing this bug:")
- **Clearer error message** — Explicitly tells user to configure API key if discovery can't access LLM

---

## v2.4.82 — 2026-08-09

### Bug Fixes & Security Hardening

#### Critical Fixes
- **P3: executor.py** — QA worker now uses `effective_repo_path` instead of `'.'` for correct execution context
- **P9: Sessionmaker** — Hoisted to ONE per phase (was one per worker call) to prevent session exhaustion
- **P4: websocket.py** — `disconnect_all()` removes socket from ALL channels (fixes connection leak)
- **P5: auth.py** — Brute-force lockout: 3 fails → 5min, doubling each tier
- **P2: self_healing.py** — Added `await dispatch` and audit orphaned 'investigate' tasks

#### Medium Priority Fixes
- **P6: bus.py** — Copy-on-write handler storage for lock-free publish
- **P8: main.py** — FTS5 double-init removed (already in init_db())
- **P11: executor.py** — `ship_with_caveats` surfaces caveats via events/results
- **P14: config.py** — Version fallback changed '2.4.23' → 'unknown'
- **P15: validation.py** — URL validated with urlparse (not bare startswith())
- **P10: tool_executor.py** — search_files regex compiled once per file (performance)
- **P12: rate_limiter.py** — Per-endpoint buckets prevent starvation
- **P13: dispatcher/engine.py** — Partial cascade vs fail-stop on node failure

---

## v2.4.81 — 2026-08-09

### Worker Maximization
- **Full soul injection** — all 9 soul fields (incl. `engineering_philosophy`, `risk_philosophy`, `collaboration_style`, `escalation_policy`) now injected into every worker's context
- **Per-worker tuning policy** — `WorkerTuningPolicy` configured per role for all 15 workers
- **Lessons loop** — `lessons_learned` entries retrieved at dispatch time
- **Self-healing upgrade** — heartbeat subscribers trigger `SelfHealingEngine`; blocked leases auto-expire

