# 47 — Navigation Specification

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Activity Bar Navigation

The activity bar is the primary navigation control. It is 48px wide, positioned left of the sidebar, and contains icon-only navigation items.

### Behavior

| Action | Result |
|---|---|
| Click rail item | Switch active view, update sidebar content, persist to store |
| Hover rail item | Tooltip with label + keyboard shortcut |
| Active item | Highlighted with accent indicator (left border or background) |
| Keyboard: Ctrl+1-6 | Switch to corresponding rail destination |

### Rail Items (exact order)

1. Home (`Ctrl+1`)
2. Mission (`Ctrl+2`)
3. Workspace (`Ctrl+3`)
4. Hermes (`Ctrl+4`)
5. Live Company (`Ctrl+5`)
6. Review Center (`Ctrl+6`)
7. (spacer)
8. Settings (`Ctrl+,`)

## Command Palette

**Source:** `components/CommandPalette.tsx`

### Activation

| Trigger | Scope |
|---|---|
| `Ctrl/Cmd+K` | Global |
| `Ctrl/Cmd+Shift+P` | Global (alias) |
| Title bar search icon | Click |

### Command Categories

| Category | Example Commands |
|---|---|
| Navigate | Go to Home, Go to Mission, Go to Workspace... |
| Mission | Create Mission, Dispatch, Cancel, Download Artifacts |
| Workspace | Open Project, Save File, Close Tab |
| Hermes | New Conversation, Switch Conversation |
| Live Company | Show Worker, Show Topology |
| Review | Show Approvals, Show Verification, Show Delivery |
| Window | Toggle Sidebar, Toggle Panel, Toggle Fullscreen |
| Settings | Open Settings, Check for Updates |

### Behavior

| Feature | Specification |
|---|---|
| Search | Fuzzy match on `label` and `id` |
| Navigation | Arrow keys + Enter, mouse hover + click |
| Dismiss | Escape or click backdrop |
| Input focus | Auto-focus on open, clear on reopen |
| Hints | Show keyboard shortcut next to label when available |

### Current Issues

1. Commands are defined inline in `App.tsx` — must be extracted to a centralized registry
2. No grouping/categories — all commands appear in flat list
3. No fuzzy search — simple `includes()` substring match
4. `?` shortcut for help fires inside text inputs — must guard

## Contextual Sidebar

### Behavior

| Rule | Implementation |
|---|---|
| Sidebar content determined by active rail | `LayoutShell` receives `sidebar` prop from `App` |
| Sidebar hidden when `sidebar` is null | CSS: `display: none` on `.ide-sidebar` |
| Sidebar width | Fixed 280px (future: resizable 240-420px) |
| Sidebar toggle | `Ctrl+B` hides/shows sidebar |

### Sidebar Content by View

| View | Sidebar |
|---|---|
| Home | Recent projects list |
| Mission | Mission list with project filter |
| Workspace | File tree (`FileTree.tsx`) |
| Hermes | Conversation list (`SidebarView.tsx`) |
| Live Company | Worker list with status dots |
| Review Center | Filter tabs + approval/event list |
| Settings | Category list |

## Bottom Panel

### Behavior

| Rule | Implementation |
|---|---|
| Default | Collapsed |
| Toggle | `Ctrl+J` or click panel header |
| Tabs | Activity, Output, Problems, Terminal |
| Resize | Future: drag header to resize (160-50% viewport) |
| Active tab | Persisted to store |

### Issues

1. "Problems" and "Output" tabs show static placeholder text — must be backed by real data or removed
2. Terminal tab is a basic input/output — not a real PTY
3. Activity tab shows raw `activityLog` strings — should format as structured timeline

## Escape Stack

When user presses Escape, dismiss in this priority order:

1. Command Palette (if open)
2. Context Menu / Dropdown (if open)
3. Modal Dialog (if open)
4. Help Overlay (if open)
5. Inspector (if open as overlay)

Never discard unsaved edits on Escape.
