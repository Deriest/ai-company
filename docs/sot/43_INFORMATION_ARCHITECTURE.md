# 43 — Information Architecture

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Top-Level Navigation (Activity Bar)

The activity bar contains exactly **7 items** (6 primary + separator + settings):

| Order | ID | Label | Icon | Context Sidebar Content |
|---|---|---|---|---|
| 1 | `home` | Home | Grid/4-squares | Recent projects, quick actions |
| 2 | `mission` | Mission | Folder/ticket | Mission list by project |
| 3 | `workspace` | Workspace | File/code | File tree + open editors |
| 4 | `hermes` | Hermes | Chat bubble | Conversation list |
| 5 | `live` | Live Company | Pulse/activity | Worker grid + filters |
| 6 | `review` | Review Center | Shield/check | Approvals, verification, delivery |
| — | — | — | Separator | — |
| 7 | `settings` | Settings | Gear | Settings categories |

## Current View → Target View Mapping

| Current View ID | Target Destination | Action |
|---|---|---|
| `welcome` | `home` (merge) | Merge welcome into Home as empty state |
| `overview` | `home` (merge) | Merge overview data into Home |
| `chat` | `hermes` | Rename only |
| `projects` | `mission` | Rename + contextual sidebar |
| `files` | `workspace` | Keep as-is |
| `live` | `live` | Keep |
| `board` | `mission` (sub-view) | Route to mission pipeline tab |
| `approvals` | `review` (sub-view) | Tab under Review Center |
| `delivery` | `review` (sub-view) | Tab under Review Center |
| `activity` | `review` (sub-view) | Tab under Review Center |
| `timeline` | `review` (sub-view) | Tab under Review Center |
| `evidence` | `review` (sub-view) | Tab under Review Center |
| `requirements` | `mission` (sub-view) | Tab under Mission |
| `workspace` (pipeline) | `mission` (sub-view) | Tab under Mission |
| `topology` | `live` (sub-view) | Tab under Live Company |
| `orchestration` | `live` (sub-view) | Tab under Live Company |
| `verification` | `review` (sub-view) | Tab under Review Center |
| `problems` | `review` (sub-view) | Tab under Review Center |
| `settings` | `settings` | Keep |
| `skills` | `settings` (sub-view) | Tab under Settings |

## View Type Union

**Before (24 views):**
```
welcome, overview, chat, projects, files, skills, settings, live, board,
approvals, delivery, activity, requirements, workspace, topology,
orchestration, verification, problems, timeline, evidence
```

**After (7 primary + sub-views):**
```
Primary: home, mission, workspace, hermes, live, review, settings
Sub-views accessed via tabs/palette only: approvals, delivery, activity,
timeline, evidence, verification, problems, topology, orchestration,
requirements, skills, board
```

## Contextual Sidebar Rules

| Active Rail | Sidebar Content | Source Component |
|---|---|---|
| Home | Quick actions list | Inline |
| Mission | Mission list + project selector | `ProjectsView` (adapted) |
| Workspace | File tree | `FileTree` |
| Hermes | Conversation list | `SidebarView` |
| Live Company | Worker list + filters | Inline |
| Review Center | Filter tabs (Needs Action, Approvals, Failures, Activity) | Inline |
| Settings | Category list | Inline |

## Object Hierarchy

```
Project
  └── Mission (Task)
        ├── Stage (FSM phase)
        │     └── Worker Lease
        │           ├── Evidence / Artifacts
        │           └── Events
        ├── Requirements
        ├── Timeline
        ├── Deliverables
        └── Approval
```

Every task/mission reference in the app deep-links to the same Mission Workspace view.
