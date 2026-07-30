# 60 — Execution Plan v2.0.2 → v2.1.0

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Milestone Overview

| Milestone | Target | Scope | Complexity | Risk |
|---|---|---|---|---|
| M1: Foundation | v2.0.2 | Version sync, dead code, font bundling | Low | Low |
| M2: Shell Unification | v2.0.3 | IA refactor, LayoutShell hardening | Medium | Medium |
| M3: Navigation & Keyboard | v2.0.4 | Command registry, shortcuts, palette | Medium | Low |
| M4: Mission Workflow | v2.0.5 | Mission Workspace, Review Center | High | Medium |
| M5: Live Company | v2.0.6 | Worker consolidation, progressive disclosure | Medium | Low |
| M6: Design Polish | v2.0.7 | Inline styles → tokens, empty states, resize | Medium | Low |
| M7: Performance & Update | v2.0.8 | Window persistence, WebSocket, update polish | Medium | Medium |
| M8: Testing & QA | v2.0.9 | Full test suite, acceptance gate validation | High | Low |
| M9: GA Release | v2.1.0 | Release artifacts, SoT sync, final validation | Low | Low |

---

## M1: Foundation (v2.0.2)

**Objective:** Eliminate version inconsistencies, dead code, and external dependencies.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 1.1 | Single version source of truth | `config.py`, `package.json`, `NSIS`, `latest.json` | All report same version |
| 1.2 | Remove duplicate console router | `backend/main.py:187` | Only one registration |
| 1.3 | Bundle fonts locally | `global.css`, `public/fonts/` | No CDN requests |
| 1.4 | Delete unused `venv` | `aic-platform/venv/` | Only `.venv` exists |
| 1.5 | Archive legacy components | `TaskDetail.tsx`, `Board.tsx` | Moved to `archive/` |
| 1.6 | Update stale docs | `README.md`, `29_PRODUCT_STATE.md` | Version matches code |

**Dependencies:** None
**Regression Risk:** Low — no functional changes
**Validation:** `tsc --noEmit`, `pytest`, `npm run build`, version grep

---

## M2: Shell Unification (v2.0.3)

**Objective:** Enforce one shell layout across all views.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 2.1 | Reduce View union to 7 primary | `types.ts` | Only 7 primary view IDs |
| 2.2 | Map all 24 views to 7 destinations | `App.tsx` | Every old view routes to new destination |
| 2.3 | Create Review Center component | New: `ReviewCenter.tsx` | Consolidates 6 views |
| 2.4 | Create Mission sub-views | `MissionWorkspace.tsx` | Requirements, pipeline, board as tabs |
| 2.5 | Create Live Company sub-views | `LiveCompany.tsx` | Topology, orchestration as tabs |
| 2.6 | Remove dead view components | Various | No orphaned imports |

**Dependencies:** M1
**Regression Risk:** Medium — view routing changes affect all navigation
**Validation:** Navigate all views, verify content accessible, `vitest` passes

---

## M3: Navigation & Keyboard (v2.0.4)

**Objective:** Implement centralized command registry and complete keyboard system.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 3.1 | Create command registry | New: `lib/commands.ts` | All commands with category, shortcut, when |
| 3.2 | Replace App.tsx inline commands | `App.tsx` | Commands from registry |
| 3.3 | Add input focus guard | `App.tsx` keydown handler | `?` doesn't fire in inputs |
| 3.4 | Implement Quick Open (Ctrl+P) | New or enhanced palette | File search in workspace |
| 3.5 | Add command categories to palette | `CommandPalette.tsx` | Grouped display |
| 3.6 | Wire Ctrl+B, Ctrl+J, Ctrl+L, Ctrl+, | `App.tsx` | All shortcuts work |
| 3.7 | Implement Escape stack | `App.tsx` | Priority dismissal |

**Dependencies:** M2
**Regression Risk:** Low — additive keyboard features
**Validation:** All shortcuts work, `?` guard tested, palette categories visible

---

## M4: Mission Workflow (v2.0.5)

**Objective:** Make Mission Workspace the canonical deep-dive surface.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 4.1 | Remove Repository tab or implement git | `MissionWorkspace.tsx` | No placeholder content |
| 4.2 | Add server-side event filter | `backend/routes/dashboard.py` | `?target=task:{id}` works |
| 4.3 | Mission Workspace as universal deep-link | All task references | Click task from any view → Mission Workspace |
| 4.4 | Mission contextual sidebar | `App.tsx`, `LayoutShell.tsx` | Mission list in sidebar |
| 4.5 | Real-time mission updates | WebSocket or polling | Mission status updates without 5s delay |

**Dependencies:** M2
**Regression Risk:** Medium — deep-link routing affects all task interactions
**Validation:** Create mission, dispatch, review evidence, approve, download ZIP

---

## M5: Live Company (v2.0.6)

**Objective:** Consolidate operational views into progressive disclosure.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 5.1 | Merge Topology into Live Company | `LiveCompany.tsx` | Department→worker visible as tab |
| 5.2 | Merge Orchestration into Live Company | `LiveCompany.tsx` | Pipeline + handoffs as tab |
| 5.3 | Worker inspector as drawer | `LiveCompany.tsx` | Click worker → inline inspector |
| 5.4 | Progressive disclosure layers | `LiveCompany.tsx` | Summary → department → worker → diagnostics |
| 5.5 | Unify worker status derivation | `LiveCompany.tsx`, API | Single source: lease-based |

**Dependencies:** M2
**Regression Risk:** Low — consolidation doesn't change data
**Validation:** Worker status matches leases, inspector shows real data

---

## M6: Design Polish (v2.0.7)

**Objective:** Achieve visual consistency and eliminate inline styles.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 6.1 | Migrate 80% inline styles to classes | All components | `grep 'style={{'` count ↓80% |
| 6.2 | Add CSS custom property for fonts | `global.css` | Single font variable |
| 6.3 | Implement empty state components | Various | Every empty screen has CTA |
| 6.4 | Implement resizable sidebar | `LayoutShell.tsx`, CSS | 240-420px drag |
| 6.5 | Implement resizable bottom panel | `LayoutShell.tsx`, CSS | 160-50% drag |
| 6.6 | Add status bar (optional) | `LayoutShell.tsx` | Compact engine/provider info |

**Dependencies:** M2
**Regression Risk:** Low — visual changes only
**Validation:** Visual inspection, no layout shifts, consistent spacing

---

## M7: Performance & Update (v2.0.8)

**Objective:** Desktop-grade persistence and update reliability.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 7.1 | Persist window bounds | `main.ts` | Restore on restart |
| 7.2 | Persist layout state | Store extensions | Sidebar width, panel height, active tab |
| 7.3 | Add native application menu | `main.ts` | File, Edit, View, Window, Help |
| 7.4 | Update URL configurability | `updateLogic.ts`, Settings | Per-install base URL |
| 7.5 | WebSocket for worker updates | `useBoot.ts`, API | Real-time without polling |
| 7.6 | Event pagination | `dashboard.py` | Cursor/offset support |

**Dependencies:** M1
**Regression Risk:** Medium — persistence changes affect boot sequence
**Validation:** Window state persists, update URL configurable, WebSocket works

---

## M8: Testing & QA (v2.0.9)

**Objective:** Full acceptance gate validation.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 8.1 | Backend test suite | `tests/` | All pass |
| 8.2 | Frontend test suite | `*.test.ts` | All pass |
| 8.3 | TypeScript validation | `tsc --noEmit` | Exit 0 |
| 8.4 | Production build | `npm run build` | Exit 0 |
| 8.5 | Acceptance gate validation | Against doc 58 | All 9 gates pass |
| 8.6 | Auto-update E2E test | Manual | v2.0.x → v2.1.0 works |
| 8.7 | Cross-platform build | NSIS, AppImage, deb | All artifacts build |

**Dependencies:** M1-M7
**Regression Risk:** Low — validation only
**Validation:** All gates from doc 58 pass

---

## M9: GA Release (v2.1.0)

**Objective:** Ship v2.1.0 with full documentation and artifacts.

### Tasks

| # | Task | Files | Acceptance |
|---|---|---|---|
| 9.1 | Bump version to 2.1.0 | All version locations | Consistent |
| 9.2 | Generate release notes | `docs/RELEASE_NOTES_v2.1.0.md` | Complete |
| 9.3 | Update SoT docs | `docs/sot/` | All accurate |
| 9.4 | Build release artifacts | `releases/AIC-ADE/` | All platforms |
| 9.5 | Generate SHA256 checksums | `SHA256SUMS.txt` | All hashes correct |
| 9.6 | Update latest.json | `releases/AIC-ADE/latest.json` | Points to v2.1.0 |
| 9.7 | Update auto-update feed | Port 8088 / production URL | Accessible |
| 9.8 | Final GA report | Root or docs | All evidence cited |

**Dependencies:** M8
**Regression Risk:** Low — build and publish only
**Validation:** Download, install, verify version, verify update works

---

## Total Estimated Complexity

| Category | LOC Changed | New Files | Deleted Files |
|---|---|---|---|
| Frontend | ~2000 | ~5 | ~15 |
| Backend | ~200 | ~0 | ~0 |
| Tests | ~500 | ~5 | ~0 |
| Documentation | ~3000 | 21 | ~0 |
| Build/Config | ~50 | ~0 | ~1 |

## Critical Path

```
M1 (Foundation) → M2 (Shell) → M3 (Keyboard) → M4 (Mission) → M8 (QA) → M9 (GA)
                                  ↓
                              M5 (Live) → M6 (Design) → M7 (Performance)
```

M1→M2→M3→M4→M8→M9 is the critical path.
M5, M6, M7 can run in parallel after M3.
