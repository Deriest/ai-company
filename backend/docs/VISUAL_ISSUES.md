# AIC Platform — Visual Issues Ledger
Last updated: 2026-07-23 continuous UI/UX loop (mobile IA + shell)

## CRITICAL
- [x] **C1 Landing 3D white canvas** — FIXED (Pillow white% 0.0 held)
- [x] **C2 Chat mobile nested-sidebar** — FIXED: list ↔ conversation (not drawer-under-drawer)
- [x] **C3 Command Center composition** — OpsTopology primary + HUD metrics

## MAJOR
- [x] **M1 Mobile Chat IA** — `mobileView` list|chat; back = Ops; 44px targets; 100dvh; safe-area composer
- [x] **M2 Dual hamburger on Chat** — removed thread hamburger; shell menu only + list/back
- [x] **M3 Settings mobile dual-nav** — horizontal section chips on <lg; desktop rail retained
- [x] **M4 Shell mobile padding** — tighter page gutters <640px; drawer width min(288px, 86vw)
- [x] **M5 CC mobile hierarchy** — gates stack order-1 on mobile; topology min-height scales down
- [~] **M6 Usage chart containers** — still conventional analytics (MODERATE residual)
- [~] **M7 Workforce roster under org map** — still card-grid secondary (MODERATE)

## MODERATE / POLISH residual
- Usage provider/model viz density
- Providers list under topology plane
- Tasks kanban on very small widths
- Live-ops motion richness when work is active (needs real traffic)

## Root-cause fixes this loop
| Issue | Root cause | Solution |
|-------|------------|----------|
| Nested sidebars on Chat mobile | Desktop dual-pane + overlay drawer | Full-screen list ↔ chat views |
| Redundant New op on Chat | Shell always showed CTA | Hide when path=/chat |
| Settings mobile stacked nav | Desktop 2-col rail compressed | Chips tablist on mobile |
| Accidental empty mobile padding | Fixed desktop page padding | @media max-width 639 page gutters |

## Evidence (CDP screenshots)
`frontend/.screenshots/`
- final-chat-list-390.png / final-chat-thread-390.png / final-chat-desktop-1440.png
- final-cc-390.png / final-cc-1440.png
- final-settings-390.png / final-tasks-390.png / final-projects-390.png
- final-workers-390.png / final-approvals-390.png / final-landing-1440.png
- loop2-* matrix earlier in session

### Interaction proof (CDP JS)
- `/chat` mobile shows Operations list + + New (no second hamburger for threads)
- + New → conversation view with **Ops** back + Send composer
- Ops back → list again
- Desktop 1440 keeps dual-pane list+main

## Verification
- `npm run build` exit 0 (tsc + vite)
- `/health` healthy · llm_configured true
- Landing white% previously 0.0 (art3); no regression intended
- pytest not installed in venv (skip); build is gate

## Convergence note
Highest-impact mobile IA defect (nested Chat sidebars) closed with architectural change, not CSS shrink.

Remaining items are polish/density, not broken IA. Further work is diminishing returns unless Usage/Workforce composition is prioritized next.
