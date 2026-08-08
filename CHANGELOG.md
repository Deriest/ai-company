# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.4.80 — 2026-08-08

### UI Redesign
- **Unified Explorer panel** — Removed redundant sidebars (FileTree + ProjectPicker from AppShell rail and duplicate session list sidebar). The right-side panel is now a clean workspace explorer with:
  - Workspace/project selector at the top
  - Real-time file search bar
  - File tree of selected project
  - Empty state prompting to pick a project if none selected
  - Auto-opens when a project exists
- **Simplified Inspector** — Replaced confusing "Deliverables/Tools/Session" tabs with focused file/workspace browsing functionality
- **Cleaner command center** — Full-width chat area without competing sidebars

---

## v2.4.79 — 2026-08-08

### Bug Fixes
- **Discovery clarification loop fix**: Chat replies like "hello" no longer re-trigger the discovery gate forever
- **Tool-chat persistence fix**: Assistant replies in tool-aware chat paths are now persisted
- **Conversation delete cascade fix**: FK cascade through engineering pipeline tables when deleting conversations
- **Improved error visibility**: Delete failures now surface alerts to users

---

## v2.4.78 — 2026-08-08

### Bug Fixes
- Conversation delete cascade fix with batch delete support
- Improved error visibility for failed deletions

---

## v2.4.77 — 2026-08-08

Full release including v2.4.77 bug fixes and improvements

---

## v2.4.71 — 2026-08-07

### Security & Auth Hardening
- Auth enforcement: `require_current_user` on ALL mutating endpoints (planning, dispatcher, delivery, autonomy, verification, context, conversations, discovery, taskgraph, orchestration, providers, backup)
