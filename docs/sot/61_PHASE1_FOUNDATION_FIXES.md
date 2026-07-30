# SoT: Phase 1 — Foundation Fixes

**Version:** 1.0.0  
**Date:** 2026-07-26  
**Status:** Active  
**Depends on:** `docs/GAP_ANALYSIS_AND_ROADMAP.md`

---

## 1. Objective

Phase 1 memperbaiki bugs kritis, menghubungkan data yang terputus, dan membuka views yang unreachable. Setelah Phase 1 selesai, aplikasi harus:

1. Semua 12+ views dapat diakses dari navigation
2. Dashboard (`WorkspaceView`) menampilkan data real dari backend
3. `AppShell` props (`health`, `modelLabel`, `alertCount`) di-wire dari `useBoot` state
4. "Chat" di-rename ke "Command Center" di semua label dan navigasi
5. Backend bugs kritis diperbaiki (duplicate LLM call, progress map, PM review gate)
6. `core.py` (1010 baris) di-split menjadi 5 route files yang terpisah
7. Intent detection di-unify ke single shared module
8. Tidak ada test regression

---

## 2. Frontend Changes

### 2.1 App.tsx — Fix 7 Unreachable Views

**Current (broken):**
```tsx
case "orchestration":
case "workflows":
case "jobs":
case "mcp":
case "memory":
case "rag":
case "automation":
  return <SettingsView initialTab={settingsTab} />;
```

**Target:**
```tsx
case "orchestration":
  return <OrchestrationView />;
case "workflows":
  return <WorkflowsView />;
case "jobs":
  return <JobsView />;
case "mcp":
  return <MCPView />;
case "memory":
  return <MemoryView />;
case "rag":
  return <RAGView />;
case "automation":
  return <AutomationView />;
```

Also fix: `case "timeline"` and `case "evidence"` should route to their own components:
```tsx
case "timeline":
  return <TimelineView />;
case "evidence":
  return <EvidenceView />;
```

### 2.2 AppShell.tsx — Rename "Chat" → "Command Center"

**Navigation array:**
```ts
// BEFORE:
{ id: "hermes", label: "Chat", icon: MessageSquare },

// AFTER:
{ id: "hermes", label: "Command Center", icon: Terminal },
```

Replace `MessageSquare` import with `Terminal` from `lucide-react`.

### 2.3 App.tsx — Wire AppShell Props

**Current (broken):**
```tsx
<AppShell
  view={view}
  onViewChange={(v: string) => setView(v as View)}
  setSettingsTab={setSettingsTab as unknown as (tab: string) => void}
  profile={profile}
>
```

**Target:**
```tsx
<AppShell
  view={view}
  onViewChange={(v: string) => setView(v as View)}
  setSettingsTab={setSettingsTab as unknown as (tab: string) => void}
  profile={profile}
  health={boot.health === "ok" ? "ok" : "bad"}
  modelLabel={boot.modelLabel || "No model"}
  alertCount={0}
>
```

### 2.4 WorkspaceView.tsx — Wire Dashboard Data

**Replace static empty arrays with API-fetched data.**

The component needs to:
1. Accept props for data (overview stats, activity, workers, projects, tasks)
2. Fetch from backend APIs on mount
3. Show real stat cards, activity feed, and missions table

**Props interface:**
```tsx
interface WorkspaceViewProps {
  onNavigate?: (view: string) => void;
}
```

**Data fetching (inside component):**
```tsx
// Fetch dashboard data from backend
const [stats, setStats] = useState<StatItem[]>([]);
const [activity, setActivity] = useState<ActivityItem[]>([]);
const [missions, setMissions] = useState<MissionItem[]>([]);

useEffect(() => {
  // Fetch from /dashboard, /tasks, /runtime/workers, /projects
  Promise.all([
    apiClient.get<DashboardData>('/dashboard'),
    apiClient.get<Task[]>('/tasks?limit=10'),
    apiClient.get<WorkerRuntime[]>('/runtime/workers'),
    apiClient.get<Project[]>('/projects'),
  ]).then(([dashboard, tasks, workers, projects]) => {
    // Build stats from response
    setStats([
      { label: 'Active Missions', value: String(tasks?.length || 0), sub: 'in progress', icon: Target, tone: 'primary' },
      { label: 'Workers Online', value: String(workers?.length || 0), sub: 'ready', icon: Users, tone: 'success' },
      { label: 'Projects', value: String(projects?.length || 0), sub: 'total', icon: GitBranch, tone: 'warning' },
      { label: 'Alerts', value: '0', sub: 'none critical', icon: BellRing, tone: 'destructive' },
    ]);
    // Build missions from tasks
    setMissions((tasks || []).map(t => ({
      id: t.id,
      title: t.title,
      phase: t.status,
      progress: t.progress || 0,
      worker: t.worker_type || 'unassigned',
      updated: t.updated_at || t.created_at,
    })));
  }).catch(() => { /* graceful degradation */ });
}, []);
```

**Wire Quick Actions:**
```tsx
const quickActions = [
  { label: 'New Mission', icon: Target, onClick: () => onNavigate?.('hermes') },
  { label: 'New Project', icon: Plus, onClick: () => onNavigate?.('mission') },
  { label: 'View Workforce', icon: UserPlus, onClick: () => onNavigate?.('live') },
  { label: 'Command Palette', icon: Command, onClick: () => {
    if ((e: KeyboardEvent) => {}) window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
  }},
];
```

### 2.5 types.ts — No changes needed

Current types already include all legacy views as `LegacyView` union type. No modifications required.

---

## 3. Backend Changes

### 3.1 Split `core.py` into 5 Route Files

Split `backend/api/routes/core.py` (1010 lines) into:

| New File | Content | Lines |
|----------|---------|-------|
| `providers.py` | Provider CRUD + test + fetch-models | ~160 |
| `conversations.py` | Conversation CRUD + search + folders + tags + export/import | ~340 |
| `messages.py` | Message CRUD | ~80 |
| `chat.py` | Chat completion + streaming + cancel + regenerate + artifacts | ~170 |
| `workers.py` | Worker runtime list/update + tools/execute | ~60 |

After splitting, `core.py` becomes a barrel file that imports and combines all sub-routers:

```python
# backend/api/routes/core.py (barrel)
from backend.api.routes.providers import router as providers_router
from backend.api.routes.conversations import router as conversations_router
from backend.api.routes.messages import router as messages_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.workers import router as workers_router

from fastapi import APIRouter

router = APIRouter()
router.include_router(providers_router)
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(chat_router)
router.include_router(workers_router)
```

### 3.2 Fix Duplicate LLM Call in Chat Streaming

**Location:** `core.py` chat/stream endpoint (currently ~lines 839-934, will be in `chat.py` after split)

**Current (broken):** When intent = task_request, `ConversationEngine.process_message()` is called, then the result is called AGAIN in the streaming block. The first call's result is discarded.

**Fix:** Call `ConversationEngine.process_message()` only once, use its result for streaming.

### 3.3 Fix Progress Map in `workflow/engine.py`

**Current (broken):**
```python
progress_map = {
    "created": 0,
    "planning": 10,
    "approval": 20,       # WRONG - not a phase
    "implementation": 50,
    "testing": 70,         # WRONG - should be "verification"
    "review": 85,          # WRONG - not a phase
    "documentation": 95,   # WRONG - should be "closeout"
    "completed": 100,
}
```

**Target:**
```python
progress_map = {
    "created": 0,
    "discovery": 5,
    "investigate": 15,
    "planning": 25,
    "implementation": 55,
    "verification": 80,
    "closeout": 95,
    "completed": 100,
    "cancelled": 0,
    "blocked": 0,
    "failed": 0,
}
```

### 3.4 Fix PM Review Gate in `workflow/engine.py`

**Current (broken):**
```python
if current == "documentation" and not pm_review_passed:
    reasons.append("PM review not passed")
```

**Target:**
```python
if current == "closeout" and not pm_review_passed:
    reasons.append("PM review not passed")
```

### 3.5 Unify Intent Detection

Create `shared/intent_patterns.py`:

```python
"""Shared intent detection patterns — single source of truth.

Used by:
- conversation/engine.py (ConversationEngine._detect_intent)
- discovery/intent.py (IntentClassifier._classify_base_intent)
"""
import re

# ── Intent constants ────────────────────────────────────
INTENT_APPROVAL = "approval"
INTENT_STATUS = "status"
INTENT_TASK_CONFIRM = "task_confirm"
INTENT_TASK_REQUEST = "task_request"
INTENT_QUESTION = "question"
INTENT_CHAT = "chat"

# ── Compiled patterns ───────────────────────────────────
APPROVAL_PATTERN = re.compile(r"\b(approve|reject|deny|accept|decline)\b", re.I)
STATUS_PATTERN = re.compile(r"\b(status|progress|how.?s it going|what.?s happening|update)\b", re.I)
CONFIRM_PATTERN = re.compile(
    r"\b(yes|ya|ok|oke|go ahead|do it|confirm|proceed|sure|setuju|lanjut|proses|"
    r"gas|kerjakan|buatkan|let'?s go|create it|make it so)\b", re.I
)
QUESTION_PATTERN = re.compile(
    r"^\b(what|how|why|when|where|who|which|can you|could you|do you|is it|are there)\b", re.I
)
TASK_VERB_PATTERN = re.compile(
    r"\b(build|create|make|fix|add|implement|deploy|refactor|develop|design|write|"
    r"generate|scaffold|set up)\b", re.I
)
TEST_TASK_PATTERN = re.compile(r"\b(write tests?|add tests?|create tests?|test the \w+)\b", re.I)


def classify_intent(content: str) -> str:
    """Classify user message intent using regex patterns.
    
    This is the canonical intent detection function.
    Both ConversationEngine and IntentClassifier should use this.
    """
    lower = content.lower().strip()

    if APPROVAL_PATTERN.search(lower):
        return INTENT_APPROVAL

    if STATUS_PATTERN.search(lower):
        return INTENT_STATUS

    words = content.split()
    if len(words) <= 6 and CONFIRM_PATTERN.search(lower):
        return INTENT_TASK_CONFIRM

    is_question = lower.endswith("?") or bool(QUESTION_PATTERN.match(lower))
    if is_question:
        return INTENT_QUESTION

    if TASK_VERB_PATTERN.search(lower) and len(words) >= 3:
        return INTENT_TASK_REQUEST

    if TEST_TASK_PATTERN.search(lower):
        return INTENT_TASK_REQUEST

    return INTENT_CHAT
```

Then update `conversation/engine.py._detect_intent()` to delegate:
```python
def _detect_intent(self, content: str) -> str:
    from shared.intent_patterns import classify_intent
    return classify_intent(content)
```

And update `discovery/intent.py._classify_base_intent()` to delegate:
```python
def _classify_base_intent(self, content: str) -> str:
    from shared.intent_patterns import classify_intent
    return classify_intent(content)
```

### 3.6 Fix `datetime.utcnow()` Deprecation

Replace all occurrences of `datetime.utcnow()` with `datetime.now(timezone.utc)` across the backend.

---

## 4. File Inventory

### Files to Create
| File | Purpose |
|------|---------|
| `aic-platform/shared/__init__.py` | New shared module |
| `aic-platform/shared/intent_patterns.py` | Unified intent detection |
| `aic-platform/backend/api/routes/providers.py` | Provider routes (from core.py) |
| `aic-platform/backend/api/routes/conversations.py` | Conversation routes (from core.py) |
| `aic-platform/backend/api/routes/messages.py` | Message routes (from core.py) |
| `aic-platform/backend/api/routes/chat.py` | Chat routes (from core.py) |
| `aic-platform/backend/api/routes/workers.py` | Worker routes (from core.py) |

### Files to Modify
| File | Changes |
|------|---------|
| `aic-ide/src/renderer/src/App.tsx` | Fix routing, wire AppShell props |
| `aic-ide/src/renderer/src/components/AppShell.tsx` | Rename Chat → Command Center |
| `aic-ide/src/renderer/src/components/WorkspaceView.tsx` | Wire dashboard data |
| `aic-platform/backend/api/routes/core.py` | Replace with barrel file |
| `aic-platform/workflow/engine.py` | Fix progress map + PM review gate |
| `aic-platform/conversation/engine.py` | Delegate to shared intent_patterns |
| `aic-platform/discovery/intent.py` | Delegate to shared intent_patterns |

### Files Unchanged
| File | Reason |
|------|--------|
| `aic-ide/src/renderer/src/types.ts` | Already correct |
| `aic-ide/src/renderer/src/hooks/useBoot.ts` | No changes needed |
| `aic-ide/src/renderer/src/lib/runtimeClient.ts` | No changes needed |
| `aic-ide/src/renderer/src/lib/api/client.ts` | No changes needed |

---

## 5. Acceptance Criteria

### Frontend
- [ ] All 12+ views reachable from navigation/sidebar
- [ ] WorkspaceView shows real stats (Active Missions, Workers Online, Projects)
- [ ] WorkspaceView shows real missions table from `/tasks` endpoint
- [ ] Quick Actions buttons navigate to correct views
- [ ] AppShell footer shows real health status and model label
- [ ] "Chat" renamed to "Command Center" everywhere (sidebar, header, menu)

### Backend
- [ ] `core.py` split into 5 route files, barrel file works
- [ ] All existing API endpoints still functional after split
- [ ] Progress map matches actual FSM phases
- [ ] PM review gate fires on "closeout" phase
- [ ] Intent detection uses single shared module
- [ ] No `datetime.utcnow()` usage remaining

### Testing
- [ ] Existing pytest suite passes (no regressions)
- [ ] Existing vitest suite passes (no regressions)
- [ ] App starts without errors (Electron + sidecar)

---

## 6. Rollback Plan

If any change breaks the system:
1. Frontend changes are isolated to 4 files — revert individually
2. Backend `core.py` barrel file can be replaced with the original monolith
3. `shared/intent_patterns.py` is additive — removing it falls back to original regex
