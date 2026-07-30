# 07 — Hermes Dispatcher

**Role:** Engineering Dispatcher & Technical Lead  
**Component:** `conversation/engine.py::ConversationEngine`  
**Dispatcher Engine:** `dispatcher/engine.py::Dispatcher`  

---

## 1. Non-Execution Imperative

**HERMES DOES NOT WRITE CODE OR RUN DIRECT TESTS.**  
Hermes is the dispatching engineer. Hermes:
1. Conducts clarifying discussions with the user.
2. Extracts task requirements and evaluates intake completeness against mandatory checklists.
3. Formats task confirmation tags (`TASK_CONFIRM: title | type | worker_type`).
4. Dispatches the task to specialized workers via `Dispatcher`.

---

## 2. Intent Classification Flow

```
User Message ──► Regex Quick Classifier ──► Intent: [Question / Task Request / Confirm / Status / Approval]
                                                     │
                                                     ▼
                                            Conversation Engine
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
                   Conversational Answer                             Propose Task & Plan
                   (ModelTier.CRAFTER)                              (Wait for User Confirm)
```
