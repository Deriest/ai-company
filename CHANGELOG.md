# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

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
