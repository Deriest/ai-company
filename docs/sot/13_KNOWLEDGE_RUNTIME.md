# 13 — Knowledge Runtime

**Subsystem:** Skills Ecosystem & Knowledge Engine  
**Files:** `backend/skill_engine.py`, `backend/routes/skills.py`  

---

## 1. Skill Architecture

Skills are procedural memory blueprints stored under `aic-skill/` and user skill paths (`~/.hermes/skills/`). Each skill contains a `SKILL.md` file with YAML frontmatter defining:
- Trigger conditions
- Required worker roles
- Step-by-step verification commands
- Known pitfalls and resolution strategies

---

## 2. Dynamic Skill Loading

When Hermes or a specialized worker begins execution, relevant skills are loaded into the system prompt context to enforce quality standards and proven execution paths.
