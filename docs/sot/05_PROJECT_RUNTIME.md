# 05 — Project Runtime

**Entity:** Project Runtime Object  
**Model:** `storage/models.py::Project`  

---

## 1. Ownership Boundary

Project Runtime is the root object in AIC-ADE. Nothing exists floating in isolation.

```
[ Project Runtime ]
  ├── Workspace Folder (Files & Git repo)
  ├── Task FSM Instances (Tasks & Deliverables)
  ├── Workers Assignment Matrix
  ├── Conversations & Message Threads
  ├── Project Memory & Context Assemblies
  └── Provider & Tier Selection
```

## 2. Project State Schema

```python
class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    path = Column(String, nullable=True) # Workspace path on host
    status = Column(String, default="active") # active, archived
    context = Column(JSON, default=dict) # Phase, health, active_workers, timeline
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

## 3. Project Context Isolation

Switching projects in the desktop UI updates `selectedProjectId` in Zustand/IPC state. All task listings, conversations, files, and worker telemetry immediately re-bind to the active `project_id`. No context leaks between projects.
