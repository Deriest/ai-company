# 12 — Memory Runtime

**Subsystem:** Persistent Context & Memory Storage  
**Files:** `backend/memory_engine.py`, `backend/routes/memory.py`  

---

## 1. Dual-Layer Memory Architecture

1. **User Memory:** Durable facts about user preferences, environment details, host operating system, and stable conventions.
2. **Project Memory:** Contextual facts scoped strictly to a project (tech stack, framework choices, architecture rules, dependency constraints).

---

## 2. Memory Ingestion & Retrieval

- Facts are stored as compact, declarative markdown snippets.
- Procedural knowledge and multi-step approaches belong in Skills (`backend/skill_engine.py`), not Memory.
