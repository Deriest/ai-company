# backend/shared/ — Shared Domain Utilities Codemap

## Overview

The `backend/shared/` module contains cross-cutting utility functions that serve as the **single source of truth** for key decision logic used across multiple subsystems (conversation engine, API routes, task executor). This directory eliminates code duplication and ensures consistent behavior between parallel implementation paths.

---

## Responsibility

This directory provides **reusable domain logic** for:

1. **Intake Completeness Evaluation** (`intake.py`) - Validates whether user input contains sufficient information to initiate a development task, using pattern-based field detection
2. **Intent Classification** (`intent_patterns.py`) - Categorizes user messages into semantic intents (approval, status inquiry, task request, question, chat) using prioritized regex matching
3. **Workspace Resolution** (`workspace.py`) - Determines the target directory/context for file operations based on explicit configuration, project association, or sandbox fallback

These utilities enforce **domain consistency** across:
- `conversation/engine.py` — ConversationEngine's streaming gate and intent detection
- `api/routes/chat.py` — /chat/execute route's clarify gate
- `discovery/intent.py` — IntentClassifier._classify_base_intent
- Task executor runtime path

---

## Design Patterns

### 1. **Singleton Utility Module Pattern**
Each `.py` file in this module acts as a centralized registry for its concern:
- `intake.py` is the canonical source for intake validation logic
- `intent_patterns.py` is the canonical source for intent classification rules
- `workspace.py` is the canonical source for workspace resolution algorithms

**Benefit**: Eliminates "triplicate" regex definitions and ensures both conversation engine and API gateway use identical business rules.

### 2. **Strategy Pattern (Intent Classification)**
The `classify_intent()` function implements a **priority chain** strategy:
```python
1. Approval detection → INTENT_APPROVAL
2. Status inquiry → INTENT_STATUS
3. Short confirm + task verbs → INTENT_TASK_CONFIRM
4. Question markers (ends with "?" or starts with question word) → INTENT_QUESTION
5. Task verb + minimum word count → INTENT_TASK_REQUEST
6. Default fallback → INTENT_CHAT
```

This allows **early exit optimization** and clear priority semantics without nested conditionals.

### 3. **Template Method Pattern (Workspace Resolution)**
`resolve_conversation_workspace()` implements a **resolution pipeline** with fixed precedence:
1. Explicit payload override (highest priority)
2. Conversation→Project linkage
3. Active local profile linkage
4. Last-used workspace hybrid cache
5. Per-scope sandbox fallback (lowest priority, sets `is_resolved=False`)

Each step follows the same pattern: attempt lookup → handle exceptions gracefully → return early on success.

### 4. **Guard Clause Pattern**
Both `evaluate_intake_completeness()` and `user_forces_task_creation()` use guard clauses:
- Normalize input upfront (`text.lower()`, `(text or "")`)
- Return immediately on negative conditions
- Defer complex logic until preconditions are satisfied

### 5. **Factory Function Pattern**
`missing_field_question()` maps missing field identifiers to human-readable clarification prompts, acting as a simple factory for localized error messaging.

### 6. **Dependency Injection**
Workspace resolution accepts dependencies as parameters rather than hardcoding imports:
- Database session (`db`) injected at runtime
- Payload data (`payload_workspace`) passed explicitly
- Enables testability and decouples from concrete infrastructure

### 7. **Sandbox Isolation Pattern**
The `sandbox_workspace_dir()` function creates isolated per-conversation directories under `$DATA_DIR/workspaces/<scope_id>`:
- Prevents cross-session contamination
- Never falls back to process cwd (explicit failure mode)
- Returns `is_resolved=False` to signal "no valid workspace" to callers

---

## Data & Control Flow

### intake.py Flow Diagram

```
User Input String
        │
        ▼
┌───────────────────────┐
│ evaluate_intake       │
│ _completeness(text)   │
└──────────┬────────────┘
           │
           ▼
    Lowercase normalization
           │
           ▼
    For each mandatory field:
    ├─ business_goal    (keywords: goal, purpose, objective...)
    ├─ target_user      (keywords: user, audience, client...)
    └─ core_features    (keywords: feature, login, api, crud...)
           │
           ▼
    Build list of missing fields
           │
           ▼
    Check force-build pattern:
    (create task, build now, langsung kerjakan...)
           │
           ▼
    if len(missing) ≤ 1 OR force-build detected:
        → (True, [])     # Complete
    else:
        → (False, [...]) # Incomplete
```

**Function Signatures:**
```python
def evaluate_intake_completeness(text_corpus: str) -> tuple[bool, list[str]]
def user_forces_task_creation(text: str) -> bool
def missing_field_question(missing_field: str) -> str | None
```

### intent_patterns.py Flow Diagram

```
User Message Content
        │
        ▼
┌───────────────────────┐
│ classify_intent()     │
└──────────┬────────────┘
           │
           ▼
    content_to_text(content)  # Normalize multi-format input
           │
           ▼
    words = content.split()
    lower = content.lower().strip()
           │
           ▼
    ┌────────────────────────────────┐
    │ PRIORITY CHECK SEQUENCE        │
    ├────────────────────────────────┤
    │ 1. Len ≤ 6 + CONFIRM_PATTERN   │
    │    → INTENT_TASK_CONFIRM       │
    ├────────────────────────────────┤
    │ 2. APPROVAL_PATTERN            │
    │    → INTENT_APPROVAL           │
    ├────────────────────────────────┤
    │ 3. STATUS_PATTERN              │
    │    → INTENT_STATUS             │
    ├────────────────────────────────┤
    │ 4. QUESTION_START_PATTERN.match()│
    │    OR ends with "?"            │
    │    → INTENT_QUESTION           │
    ├────────────────────────────────┤
    │ 5. TASK_VERB_PATTERN + len≥3   │
    │    OR TEST_TASK_PATTERN        │
    │    → INTENT_TASK_REQUEST       │
    └────────────────────────────────┘
           │
           ▼
    Else → INTENT_CHAT (fallback)
```

**Intent Constants:**
```python
INTENT_APPROVAL = "approval"
INTENT_STATUS = "status"
INTENT_TASK_CONFIRM = "task_confirm"
INTENT_TASK_REQUEST = "task_request"
INTENT_QUESTION = "question"
INTENT_CHAT = "chat"
```

### workspace.py Flow Diagram

```
resolve_conversation_workspace(
    db,                 # SQLAlchemy database session
    payload_workspace,  # Optional: explicit workspace from caller
    conversation_id     # Required: conversation identifier
)
        │
        ▼
    IF payload_workspace exists and non-empty:
        → (payload_workspace, True)  # Explicit wins
        │
        ▼
    Lookup Conversation conv via db.get(Conversation, conversation_id)
        │
        ├─ If conv.project_id exists:
        │   │
        │   ▼
        │   repo_path = await _project_repo_path(db, conv.project_id)
        │   │
        │   └─ If repo_path found:
        │       → (repo_path, True)
        │
        ▼
    Try LocalProfile.active_project_id lookup
        │
        ├─ If prof.active_project_id exists:
        │   │
        │   ▼
        │   repo_path = await _project_repo_path(db, prof.active_project_id)
        │   │
        │   └─ If repo_path found:
        │       → (repo_path, True)
        │
        ▼
    Try LocalProfile.last_used_repo_path hybrid cache
        │
        ├─ If last_used_repo_path exists AND directory still present:
        │   │
        │   ▼
        │   → (last_used_repo_path, True)  # User convenience optimization
        │
        ▼
    Fallback: sandbox_workspace_dir(conversation_id)
        │
        ▼
    Create $DATA_DIR/workspaces/<conversation_id>/ if not exists
        │
        ▼
    → (sandbox_path, False)  # Sandbox mode: no workspace chosen
```

---

## Integration Points

### Direct Consumers

| Module | Usage Context | Imported Functions |
|--------|---------------|-------------------|
| `conversation/engine.py` | ConversationEngine._handle_task_request | `evaluate_intake_completeness()`, `user_forces_task_creation()` |
| `conversation/engine.py` | ConversationEngine._detect_intent | All pattern constants + `classify_intent()` |
| `api/routes/chat.py` | /chat/execute streaming gate | `evaluate_intake_completeness()`, `user_forces_task_creation()` |
| `discovery/intent.py` | IntentClassifier._classify_base_intent | Pattern constants + `classify_intent()` |
| Task executor runtime | Workspace context setup | `resolve_conversation_workspace()`, `sandbox_workspace_dir()` |

### Dependencies

#### Runtime Dependencies
```python
# intake.py
import re                           # Standard library

# intent_patterns.py
import re                           # Standard library
from backend.services.content_utils import content_to_text  # Internal service

# workspace.py
import logging                      # Standard library
from pathlib import Path            # Standard library
from backend.config import settings # Internal config
from storage.models import Project  # ORM models
from storage.models import Conversation  # ORM models
from backend.models.local_profile import LocalProfile  # ORM models
from sqlalchemy import select       # ORM query builder
```

#### External Package Dependencies
- `sqlalchemy` — Async database queries for workspace resolution
- No third-party regex libraries (all use built-in `re` module)

### API Surface

#### Public Functions

| Function | Module | Return Type | Purpose |
|----------|--------|-------------|---------|
| `evaluate_intake_completeness(text_corpus: str)` | intake | `tuple[bool, list[str]]` | Validate requirement completeness |
| `user_forces_task_creation(text: str)` | intake | `bool` | Detect urgent build requests |
| `missing_field_question(missing_field: str)` | intake | `str \| None` | Generate clarification prompt |
| `classify_intent(content: str)` | intent_patterns | `str` | Route message to handler |
| `resolve_conversation_workspace(db, payload_workspace, conversation_id)` | workspace | `tuple[str, bool]` | Resolve target directory |
| `sandbox_workspace_dir(scope_id)` | workspace | `str` | Create isolated sandbox path |

#### Constants

| Constant | Module | Value Range | Purpose |
|----------|--------|-------------|---------|
| `INTENT_APPROVAL` | intent_patterns | `"approval"` | Approve/reject actions |
| `INTENT_STATUS` | intent_patterns | `"status"` | Progress inquiries |
| `INTENT_TASK_CONFIRM` | intent_patterns | `"task_confirm"` | Short affirmative confirmations |
| `INTENT_TASK_REQUEST` | intent_patterns | `"task_request"` | Explicit build commands |
| `INTENT_QUESTION` | intent_patterns | `"question"` | Interrogative queries |
| `INTENT_CHAT` | intent_patterns | `"chat"` | Conversational fallback |

---

## Regex Patterns Summary

### Mandatory Intake Fields (intake.py)

```python
business_goal: r"\b(goal|purpose|objective|why|app to|site to|website for|buatkan|untuk|tujuan|aplikasi|sistem|aplikasi ini|project)\b"
target_user: r"\b(user|users|audience|people|client|customer|admin|developer|pengembang|pelanggan|pengguna|masyarakat|umum|untuk siapa)\b"
core_features: r"\b(feature|features|allow|function|receive|send|auth|login|button|api|crud|fitur|section|table|form|gallery|kontak|lokasi|sistem|dashboard|database|user|payment|notification)\b"
```

### Force-Build Triggers (intake.py)

```python
_force_build_pattern: r"\b(create task|build now|start task|start build|create task to|langsung kerjakan|gas sekarang|mulai sekarang|kerjakan sekarang)\b"
_force_task_pattern: r"\b(create task|build now|start task|start build|create the task|just do it|do it now|implement now|kerjakan sekarang|buat task|langsung kerjakan|gas sekarang)\b"
```

### Intent Detection Patterns (intent_patterns.py)

```python
APPROVAL_PATTERN: r"\b(approve|reject|deny|accept|decline|setuju|tolak|terima|iya)\b"
STATUS_PATTERN: r"\b(status|progress|how.?s it going|what.?s happening|update|kemajuan|progres|perkembangan)\b"
CONFIRM_PATTERN: r"\b(yes|ya|ok|oke|go ahead|do it|confirm|proceed|sure|setuju|lanjutkan?|proses|gas|let'?s go|create it|make it so)\b"
QUESTION_START_PATTERN: r"^\b(what|how|why|when|where|who|which|can you|could you|do you|is it|are there|bagaimana|apa|kenapa|mengapa|kapan|dimana|siapa|mana|bisakah|bisa)\b"
TASK_VERB_PATTERN: r"\b(build|create|make|fix|add|implement|deploy|refactor|develop|design|write|generate|scaffold|set\s*up|document|optimize|improve|update|change|configure|setup|install|remove|delete|rename|move|copy|extract|merge|bangun|buat|perbaiki|tambah|terapkan|kembangkan|rancang|tulis|kerjakan|buatkan|pasang|hapus|pindah|salin|gabung|debug|profil|audit|tes|test|review|inspect|analisis|analyze)\b"
TEST_TASK_PATTERN: r"\b(write tests?|add tests?|create tests?|test the \w+|tulis test|tambah test|buat test|tes)\b"
```

---

## Evolution Notes

### Current State
- Clean separation of concerns: each file handles one domain
- Single-source-of-truth documented in module docstrings
- Consistent error handling via try/except blocks that log but don't fail
- Hybrid approaches where needed (e.g., `last_used_repo_path` in workspace.py)

### Technical Debt Mitigated
- Eliminated duplicate regex definitions across ConversationEngine, IntentClassifier, and API routes
- Fixed regression where workspace resolution incorrectly fell back to process cwd
- Replaced 6 mandatory intake fields with pragmatic 3-field model (more conversational)
- Unified intent priority logic across async/sync code paths

---

## Testing Considerations

While test files are excluded from this analysis, the design supports:
- Unit tests for pattern matching against known good/bad inputs
- Property tests for intent classification consistency
- Integration tests for workspace resolution edge cases (missing projects, deleted paths)
- Mockable dependencies (DatabaseSession injected at runtime)
