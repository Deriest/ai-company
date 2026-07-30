# AIC IDE — Vertical Implementation Plan

## Phase 0 ✅
- Forensics, ADR Electron, architecture, IA/design tokens

## Phase 1 — Desktop shell + runtime
- Electron main/preload/renderer scaffold
- Secure IPC: dialogs, paths, open external, store
- Runtime client: health, login, settings URL
- Welcome + shell chrome + command palette skeleton
- Live Company rail (15 static + API overlay)

## Phase 2 — Conversation + projects
- Project list/create via API
- Conversation SSE to Hermes
- Overview from task/project state

## Phase 3 — Live execution
- Workers + leases + events
- Worker inspector (activity/outputs/files; terminal honest empty)
- Realtime WS + poll fallback

## Phase 4 — Files + editor
- Workspace file tree via API + local root optional
- Monaco editor (read/write with care)
- Diff later

## Phase 5 — Board + activity
- FSM board from real task status
- Timeline from Event table

## Phase 6 — Requirements/context
- REQUIREMENTS.md + structured fields

## Phase 7 — Verification + delivery
- Evidence panels, download ZIP, open folder

## Phase 8 — Hardening
- path/process abstractions, packaging, CI matrix, security

## Phase 9 — E2E + web parity matrix
- Golden path, multi-worker evidence, web retirement decision

## Web retirement
KEEP WEB AS FALLBACK until matrix proves replacement.
