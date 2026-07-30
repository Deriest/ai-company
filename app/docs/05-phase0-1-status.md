# Phase 0–1 Status (2026-07-23)

## Phase 0 — Done

| Artifact | Path |
|----------|------|
| Forensics | `docs/00-forensic-investigation.md` |
| ADR Electron | `docs/01-adr-desktop-technology.md` |
| Architecture | `docs/02-architecture.md` |
| IA + design tokens | `docs/03-ia-design-system.md` |
| Plan | `docs/04-implementation-plan.md` |

### Key forensic facts
- 15 canonical workers verified in `canonical_workforce.py`
- FSM: created→investigate→planning→implementation→verification→closeout→completed
- Production executor: `executor_simple.py` (sequential, LLM/template workers)
- **No real PTY worker streams** in core today — IDE must not fake terminals
- Execution identity ≈ **Lease** + Event + workspace files
- Backend healthy: version 1.0.0, llm configured
- Live API: `/api/workers` returns **15** workers (Hermes…Sentinel)

### Tech decision
**Electron + React + TS** (Rust/Tauri not available on host; node-pty path for user terminal later).

## Phase 1 — Scaffold complete (build verified)

| Check | Result |
|-------|--------|
| `npm run build` (tsc electron + vite) | PASS |
| dist + dist-electron emitted | PASS |
| API health/login/workers via node client | PASS (15 workers, 1 project, 38 tasks) |
| Electron window interactive GUI | NOT run headless in this session (DISPLAY may be limited) |
| Web SPA modified | NO — new tree `aic-ide/` only |
| Web retirement | KEEP WEB AS FALLBACK |

## What the app does now
- Greenfield shell (title / rail / main / Live Company / dock)
- Command palette Ctrl/Cmd+K
- Runtime settings + JWT login to aic-platform
- Projects/tasks list from real API
- Live Company: all 15 canonical IDs overlayed with `/api/workers` status
- Worker inspector: honest empty terminal message
- Chat: SSE stream with non-stream fallback
- Local folder open via native dialog (Electron bridge)

## Not done (next)
- Monaco editor, board FSM UI, requirements center, delivery ZIP from IDE, node-pty user terminal, packaging smoke, full golden-path E2E in Electron window

## Verdict so far
**AIC IDE DEVELOPMENT BUILD** — not alpha until chat→task→live worker evidence is exercised end-to-end inside the desktop shell with screenshots.
