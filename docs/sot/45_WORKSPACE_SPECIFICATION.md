# 45 — Workspace Specification

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Workspace = The Primary Focus

The Workspace occupies the largest area of the shell. It is where the user does actual work: reading code, reviewing deliverables, editing files, and inspecting mission artifacts.

## Workspace Modes

| Mode | Trigger | Content |
|---|---|---|
| **Welcome** | No project open, first launch | Quick actions, recent projects, provider status |
| **Editor** | File selected from File Tree | CodeMirror editor with syntax highlighting |
| **Mission Workspace** | Mission selected from Mission list | Mission detail with tabs (overview, timeline, evidence, repository) |
| **Hermes Chat** | Chat view active | Conversation messages + composer |
| **Live Company** | Live rail active | Worker grid, department view, inspector |
| **Review Center** | Review rail active | Approvals, verification, delivery, activity tabs |
| **Settings** | Settings rail active | Provider config, update settings, about |

## Mission Workspace (Primary Deep-Dive Surface)

**Source:** `components/MissionWorkspace.tsx`

### Tabs

| Tab | Content | Evidence |
|---|---|---|
| Overview | Objectives, adaptive runtime profile, workers, health | `task.description`, `task.context.adaptive_runtime` |
| Timeline | Event stream filtered to this mission | `api.events()` filtered by `task:{id}` |
| Evidence | Workspace files + file content viewer | `api.taskWorkspaceFiles()`, `api.taskWorkspaceContent()` |
| Repository | Git state, changed files, commits | Placeholder — must be implemented |

### Current Issues (from investigation)

1. **Repository tab is a placeholder** — shows only `Project Path: {repo_path}`. Must either implement real git integration or remove the tab.
2. **Timeline filters in-memory** — `events.filter(e => e.target.includes(taskId))` on client side. Should be server-side filter.
3. **No task inspector deep-link** — clicking a task from different views opens different screens instead of the same Mission Workspace.
4. **Progress bar uses inline styles** — should use design system tokens.

## File Editor

**Source:** `components/CodeEditor.tsx`, `components/FilesView.tsx`

| Feature | Status |
|---|---|
| Syntax highlighting | CodeMirror with language detection |
| Dark theme | Custom `EditorView.theme()` matching deep-void |
| File tree | `FileTree.tsx` with context menu (AST analyze) |
| Tab management | Multi-tab with dirty indicator |
| Save | Ctrl+S wired via global keyboard handler |

### Issues

1. **No Quick Open (Ctrl+P)** — advertised in `FilesView` but not implemented in global handler
2. **File tree context menu** has AST analyze but no other actions (rename, delete, reveal in OS)

## Empty State Rules

| State | Required Content |
|---|---|
| No project | "Open a project folder to get started" + CTA |
| No files | "This mission hasn't produced any files yet" + context |
| No editor open | Welcome screen or last-used view |
| Loading | Skeleton or "Loading..." with timeout fallback |
| Error | Specific error message + retry button |
