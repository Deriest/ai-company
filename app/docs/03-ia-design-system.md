# AIC IDE — Information Architecture & Design System (Greenfield)

## Product principle

Desktop operating environment for an autonomous AI software company.
Not a SaaS dashboard. Not VS Code clone. Not 15 chatbots.

## Navigation model

### Global chrome
- **Title bar:** AIC IDE · project name · branch (if git) · runtime health · controls
- **Activity rail (left, 48px):** Home · Projects · Chat · Files · Search · Live · Settings
- **Main stage:** context-dependent workspace
- **Live Company rail (right, 280px collapsible):** all 15 workers + summary counts
- **Bottom dock (collapsible):** Problems · Output · Terminal · Activity

### Surfaces

| Surface | Purpose |
|---------|---------|
| Welcome | Empty state: talk to Hermes, recent projects, open/new |
| Project Overview | Phase, now, who works, blocked, needs action |
| Conversation | Hermes chat (SSE) |
| Live Execution | Company board + worker inspector |
| Files | Tree + editor |
| Board | FSM phases + tasks (authoritative FSM) |
| Requirements | Structured + REQUIREMENTS.md |
| Verification | Build/test/QA evidence |
| Delivery | Open folder / export ZIP |
| Settings | Runtime URL, providers (via API), shortcuts |

### Command palette (Ctrl/Cmd+K)
Actions must call real handlers: New Project, Open Project, Talk to Hermes, Search Files, Go to Worker, Open Live, Terminal, Verification, Download, Settings.

## Design tokens (independent of web)

```
--void:        #05060A
--surface-0:   #0A0C12
--surface-1:   #10141C
--surface-2:   #161C28
--line:        rgba(255,255,255,0.08)
--line-strong: rgba(255,255,255,0.14)
--text-1:      #E8ECF4
--text-2:      #9AA3B5
--text-3:      #5C6578
--accent:      #3DDC97   /* signal green — operational */
--accent-2:    #5B8CFF   /* cool blue — focus */
--warn:        #F0B429
--danger:      #F07178
--idle:        #3A4150
font-ui:       "IBM Plex Sans", system-ui, sans-serif
font-mono:     "IBM Plex Mono", ui-monospace, monospace
radius:        6px
density:       compact IDE (not card-farm)
```

Rules:
- No glassmorphism soup
- No cyan-border-everywhere admin look from web SPA
- Glow only on live status dots
- 3D only on Welcome optional hero — never over editor/terminal

## Worker status colors

| State | Dot |
|-------|-----|
| WORKING | accent pulse |
| WAITING | warn |
| FAILED | danger |
| IDLE | idle |
| COMPLETED recent | accent solid |

## Layout persistence
window bounds, rail widths, dock height, last project, open tabs → electron-store or app-data JSON.
