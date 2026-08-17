# 44 — User Journeys

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Journey 1: First Launch (Provider Onboarding)

```
Open App → Splash Screen → Health Check Polling → Home (empty state)
  → "Configure Provider" CTA
  → Settings → Provider Settings
  → Add Provider (name, base_url, API key, model)
  → Test Connection (shows model count)
  → Save → Return to Home
  → Home shows "Start with Hermes" CTA
```

**Acceptance:** User configures one provider and sees model count within 60 seconds of first launch.

## Journey 2: Create & Execute Mission (Primary Workflow)

```
Home → "Start with Hermes" (or Ctrl+L)
  → Hermes Chat: "Build a REST API for user management"
  → Hermes asks clarifying questions (intent → task_request)
  → User confirms → TASK_CONFIRM parsed → Task created
  → Chat shows "Mission created: user-mgmt-api"
  → Switch to Mission rail (Ctrl+2)
  → Mission list shows new mission with status "created"
  → Click mission → Mission Workspace opens
  → Click "Dispatch" → status changes to "planning"
  → Workers start executing (visible in Live Company)
  → Timeline populates with events
  → Mission progresses through FSM phases
  → "verification" → user reviews evidence
  → "completed" → Download Artifacts button available
```

**Acceptance:** Full dispatch-to-completion cycle produces real deliverables and events.

## Journey 3: Review & Approve Work

```
Mission → status "approval" (blocked on approval)
  → Review Center → "Needs Action" tab shows pending approval
  → Click approval → Mission Workspace opens with approval context
  → User reviews evidence, files, events
  → Approve / Reject
  → If approved: mission continues to next phase
  → If rejected: mission moves to "blocked" or "failed"
```

**Acceptance:** Approval workflow blocks and unblocks mission execution correctly.

## Journey 4: Browse & Edit Workspace Files

```
Workspace rail (Ctrl+3)
  → File tree shows project files
  → Click file → CodeMirror editor opens in workspace
  → Edit, save (Ctrl+S)
  → File tree reflects changes
  → Bottom panel shows terminal (Ctrl+J to toggle)
  → Run commands in terminal
```

**Acceptance:** File browsing, editing, and terminal work without leaving the shell.

## Journey 5: Monitor Live Company

```
Live Company rail (Ctrl+5)
  → Worker grid shows 15 canonical workers
  → Active workers pulse with current task
  → Click worker → Inspector opens (right panel)
  → Inspector shows: role, task, progress, events, artifacts
  → Timeline tab shows event stream filtered by worker
  → Topology tab shows department → worker hierarchy
```

**Acceptance:** Worker status updates in real-time. Inspector shows meaningful data only.

## Journey 6: Auto-Update

```
App starts → UpdateManager checks http://host:port/latest.json
  → If newer version available:
    → Title bar shows "↑ Update Ready" badge
    → Settings → Update section shows version, notes, download button
    → Click "Download" → progress bar with speed/size
    → SHA256 verification runs automatically
    → "Install" button appears
    → Click "Install" → installer launches → app restarts
  → If up-to-date: silent, no UI noise
```

**Acceptance:** Update cycle works from v2.0.x to v2.1.0 with SHA256 verification.

## Journey 7: Keyboard-Only Operation

```
Ctrl+K → Command Palette → type "mission" → Enter → Mission view
Ctrl+1-6 → Switch rail destinations
Ctrl+B → Toggle sidebar
Ctrl+J → Toggle bottom panel
Ctrl+L → Focus Hermes
Ctrl+, → Settings
? → Keyboard shortcuts overlay (only when not in text input)
Escape → Dismiss topmost overlay (palette → modal → help)
```

**Acceptance:** All primary workflows completable without mouse.
