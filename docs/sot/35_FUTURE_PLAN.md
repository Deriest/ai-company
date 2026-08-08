# 35 — Future Plan

**Objective:** Make AIC-ADE the simplest *complete* way to run an AI engineering company on your own machine.
**Status:** Draft v1 (2026-08-09) · supersedes the "Future Vision" section of `30_ROADMAP.md`

---

## 1. Positioning

Most tools in this space are **agent harnesses** (e.g., Orca): they give *you* terminals, worktrees, and browsers, and you run external CLI agents (Claude Code, Codex, OpenCode) inside them. Powerful but complicated — because the human is still the manager of every agent.

AIC-ADE is different: it **is the company**. The app doesn't host agents, it *employs* workers. The user acts as Executive Director handing over missions, not as an operator babysitting terminals.

So this plan does not copy Orca feature-for-feature. It takes the ideas that make Orca feel *complete* — isolation, review, git, parallelism, visibility — and translates them into company terms, keeping the product surface small.

### What we learn from Orca (and what we take)

| Orca idea | Why it feels good | AIC-ADE version (simpler) |
|---|---|---|
| Parallel worktrees | Agents never step on each other | One git worktree per dispatched task, managed automatically |
| Diff review + annotation | Human stays in control | Approve/reject flow on delivered diffs |
| Real terminals | Transparency | One PTY panel showing worker shell sessions |
| Task board | Visibility over parallel work | Mission/task board on top of the existing dispatcher |
| Mobile companion | Monitor from anywhere | Optional read-only local status page (later, off by default) |
| 25+ external CLI agents | Flexibility | **Not adopted** — the company has its own workforce; extend via plugins/MCP |

---

## 2. Guiding principles (kept simple)

1. **One app, one concept: the company.** Every feature must answer: "which worker or department does this help?"
2. **Local-first stays absolute.** No cloud, no accounts, no multiplayer. Anything network-facing is opt-in.
3. **Control surfaces over feature surfaces.** Prefer review / approve / rollback over adding new capabilities.
4. **No editor wars.** AIC-ADE is not VS Code. Lightweight built-in viewing/editing only.
5. **Evidence, not claims.** Every delivered task shows what changed, what was verified, what it cost.

---

## 3. Phase plan

### v2.5 — Trust & Control (near term)
Theme: make it safe to let workers touch real code.

| # | Feature | What | Why |
|---|---|---|---|
| F1 | Real PTY terminal | Replace fake terminal panel with node-pty; live view of worker shell sessions | TD-10, transparency |
| F2 | Diff review flow | Per-file diff view with approve/reject; rejected changes revert cleanly | user control |
| F3 | Git basics | status / branch / diff / commit in project panel; workers propose commits | TD-4 placeholder tab |
| F4 | Session & error recovery | Resume interrupted tasks; retry/skip decisions on failed tool calls | roadmap Phase C |
| F5 | Palette & shortcut polish | Categorized command palette, keybindings for the review flow | TD-12 |

### v2.6 — The Parallel Company
Theme: many tasks moving at once, none colliding.

| # | Feature | What | Why |
|---|---|---|---|
| F6 | Task worktrees | Each dispatched task auto-gets its own git worktree; delivery = mergeable branch | Orca's core idea, in company terms |
| F7 | Mission board | Kanban-style board: missions → tasks → status, one click into the office floor | visibility |
| F8 | Live events over WebSocket | Replace polling for worker status and task progress | TD-16 |
| F9 | Cost & budget panel | Per-project token/cost usage with budget warnings | pricing service already exists |

### v3.0 — The Complete Company
Theme: a company you can delegate to, end to end.

| # | Feature | What | Why |
|---|---|---|---|
| F10 | Evidence bundles | Every delivered task ships diff + test results + report | verification engine needs UX |
| F11 | Lessons loop | Failed tasks feed `lessons_learned` back into worker skills/prompts | the company gets smarter |
| F12 | Mission templates | Reusable scaffolds ("REST API", "Bug fix", "Refactor") | TD-22 |
| F13 | Offline-first polish | First-class Ollama/LM Studio setup, near-zero config | local-first promise |
| F14 | Optional status page | Read-only, LAN-only, off by default — check missions from a phone | minimal answer to mobile companion |

---

## 4. Non-goals (kept simple by design)

- **Not** a general-purpose IDE/editor.
- **Not** a host for external CLI agents (Claude Code, Codex, etc.) — extend the workforce via plugins/skills/MCP instead.
- **No** cloud sync, accounts, or multiplayer collaboration.
- **No** native mobile app — at most F14's read-only page.
- **No** GitHub/Linear-style issue management beyond local git operations.

---

## 5. Success criteria

- **v2.5** — a user can let a worker edit a real project, review every change, and roll back, confidently.
- **v2.6** — 3+ tasks run in parallel on one repo without file conflicts, all visible on one board.
- **v3.0** — a mission goes brief → delivery while the human only appears at approval points.

---

## 6. Housekeeping

- `30_ROADMAP.md` Phases A–C are stale: most "Planned" items shipped by v2.4.x (real tool execution, file tree/explorer, workspace folders, context pipeline). Needs an audit and merge with this plan.
- `34_FUTURE_VISION.md` stays the north star; this document is the concrete path toward it.
