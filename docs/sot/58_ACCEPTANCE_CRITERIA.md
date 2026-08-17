# 58 — Acceptance Criteria

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Gate 1: Shell Consistency

| Criterion | Validation |
|---|---|
| Every screen uses the same shell layout | Visual inspection: no view bypasses LayoutShell |
| Activity bar has exactly 7 items | Code inspection: `LayoutShell.tsx` nav items |
| Context sidebar changes per view | Navigate all views, verify sidebar content changes |
| Bottom panel is collapsed by default | Fresh install → panel hidden |
| No floating component overlaps | Manual testing: palette, modals, dropdowns |

## Gate 2: Information Architecture

| Criterion | Validation |
|---|---|
| 24 views reduced to 7 primary + sub-views | `types.ts` View union has 7 primary values |
| Command palette lists all commands with categories | Palette shows grouped commands |
| Every deep-link opens Mission Workspace | Click task from any view → same Mission Workspace |
| Settings is a single unified view | No standalone Skills/Update views in rail |

## Gate 3: Keyboard System

| Criterion | Validation |
|---|---|
| Ctrl+K opens command palette | Works globally |
| Ctrl+P opens Quick Open (file search) | Works in Workspace view |
| Ctrl+B toggles sidebar | Works globally |
| Ctrl+J toggles bottom panel | Works globally |
| Ctrl+L focuses Hermes | Opens Hermes view + focuses composer |
| Ctrl+, opens Settings | Works globally |
| Ctrl+1-6 switches rail | Works globally |
| `?` does NOT fire in text inputs | Type `?` in chat → no help overlay |
| Escape dismisses overlays in priority order | Palette → modal → help |

## Gate 4: Mission Workflow

| Criterion | Validation |
|---|---|
| Create mission via Hermes conversation | Chat → intent → task created |
| Dispatch mission → worker executes | Dispatch → lease → deliverables |
| Evidence tab shows real workspace files | Files exist and are readable |
| Timeline shows mission-specific events | Events filtered to task |
| Download produces valid ZIP | ZIP contains workspace files |

## Gate 5: Provider & Runtime

| Criterion | Validation |
|---|---|
| Add provider → test → activate | Full CRUD works |
| Model discovery returns capabilities | Adaptive runtime profile generated |
| Fallback works on provider error | 429/503 triggers fallback chain |

## Gate 6: Update System

| Criterion | Validation |
|---|---|
| Manifest fetch works | `GET /latest.json` returns valid manifest |
| Version comparison correct | `2.0.2 > 2.0.1` → true |
| SHA256 verification passes | Downloaded file matches hash |
| Install launches installer | NSIS/AppImage starts |
| Settings shows update status | Current version, last checked, channel |

## Gate 7: Design System

| Criterion | Validation |
|---|---|
| No Google Fonts CDN dependency | Fonts bundled or system fallback |
| All inline styles migrated to tokens | `grep 'style={{'` count decreases by 80% |
| Consistent 8px spacing | Visual inspection: no random gaps |
| One button system | All buttons use .primary/.secondary/.danger |
| Empty states have guidance | Every empty screen shows CTA |

## Gate 8: Testing & Build

| Criterion | Validation |
|---|---|
| Backend pytest passes | `pytest tests/ -q` → all pass |
| Frontend vitest passes | `npx vitest run` → all pass |
| TypeScript clean | `npx tsc --noEmit` → exit 0 |
| Production build works | `npm run build` → exit 0 |
| Version consistent | package.json = config.py = NSIS = latest.json |

## Gate 9: Performance

| Criterion | Validation |
|---|---|
| App cold start < 3 seconds | Measured on target hardware |
| Mission list loads < 1 second | 100 missions, measured |
| File tree loads < 500ms | 200 files, measured |
| No layout shifts on navigation | Visual inspection |
