# 49 — Component Library

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Component Inventory

### Shell Components

| Component | File | LOC | Purpose | Status |
|---|---|---|---|---|
| `LayoutShell` | `LayoutShell.tsx` | 327 | Root shell with all structural regions | Production |
| `CommandPalette` | `CommandPalette.tsx` | 90 | Modal command overlay | Production (basic) |
| `UpdateBanner` | `UpdateBanner.tsx` | ~80 | Update notification bar | Production |
| `Splash` | `Splash.tsx` | ~60 | Boot/loading screen | Production |

### View Components

| Component | File | LOC | Purpose | Status |
|---|---|---|---|---|
| `App` | `App.tsx` | 305 | View router and state coordinator | Production (needs refactor) |
| `Overview` | `Overview.tsx` | 186 | Home dashboard | Production |
| `ChatView` | `ChatView.tsx` | 195 | Hermes conversation | Production |
| `SidebarView` | `SidebarView.tsx` | ~83 | Conversation list | Production |
| `ProjectsView` | `ProjectsView.tsx` | ~200 | Mission list | Production |
| `MissionWorkspace` | `MissionWorkspace.tsx` | 314 | Mission detail with tabs | Production (repo tab placeholder) |
| `FilesView` | `FilesView.tsx` | 217 | File explorer + editor | Production |
| `FileTree` | `FileTree.tsx` | ~150 | File tree with context menu | Production |
| `CodeEditor` | `CodeEditor.tsx` | ~100 | CodeMirror wrapper | Production |
| `LiveCompany` | `LiveCompany.tsx` | 200 | Worker grid overview | Production |
| `ProviderSettings` | `ProviderSettings.tsx` | 409 | Provider CRUD + model fetch | Production |
| `UpdateSettings` | `UpdateSettings.tsx` | ~100 | Update config + check | Production |

### Legacy/Unused Components (Candidates for Removal)

| Component | File | Issue |
|---|---|---|
| `TaskDetail` | `TaskDetail.tsx` | Superseded by `MissionWorkspace` — check for dead imports |
| `Board` | `Board.tsx` | Workflow board — duplicates mission pipeline |
| `Approvals` | `Approvals.tsx` | Standalone approvals — should merge into Review Center |
| `Delivery` | `Delivery.tsx` | Standalone delivery — should merge into Review Center |
| `ActivityTimeline` | `ActivityTimeline.tsx` | Standalone timeline — should merge into Review Center |
| `AuditView` | `AuditView.tsx` | Standalone audit — should merge into Review Center |
| `Requirements` | `Requirements.tsx` | Standalone requirements — should merge into Mission tabs |
| `Topology` | `Topology.tsx` | Static hierarchy — should merge into Live Company |
| `Orchestration` | `Orchestration.tsx` | Complex pipeline view — should merge into Live Company |
| `Verification` | `Verification.tsx` | Standalone verification — should merge into Review Center |
| `Problems` | `Problems.tsx` | Standalone problems — should merge into Review Center |
| `ProjectWorkspace` | `ProjectWorkspace.tsx` | Pipeline view — duplicates MissionWorkspace tabs |
| `WorkerInspector` | `WorkerInspector.tsx` | Worker detail — should be a panel/drawer, not a page |
| `SkillsManager` | `SkillsManager.tsx` | Skill management — should be Settings sub-view |

### Hook Components

| Hook | File | Purpose |
|---|---|---|
| `useBoot` | `hooks/useBoot.ts` | App lifecycle, health, providers, updates |
| `useChat` | `hooks/useChat.ts` | Conversation state, messages, send |
| `useWorkspace` | `hooks/useWorkspace.ts` | Project, tasks, workers, file management |

## Refactoring Strategy

### Phase 1: Consolidate Review Center
Merge `Approvals`, `Delivery`, `Verification`, `Problems`, `ActivityTimeline`, `AuditView` into a single `ReviewCenter` component with tab navigation.

### Phase 2: Consolidate Live Company
Merge `Topology`, `Orchestration`, `WorkerInspector` into `LiveCompany` with progressive disclosure layers.

### Phase 3: Consolidate Mission
Merge `Requirements`, `ProjectWorkspace`, `Board` into `MissionWorkspace` tabs.

### Phase 4: Remove Dead Code
Delete `TaskDetail.tsx` and any other components that are no longer imported.

### Phase 5: Extract Command Registry
Move command definitions from `App.tsx` into a dedicated `lib/commands.ts` with typed metadata.
