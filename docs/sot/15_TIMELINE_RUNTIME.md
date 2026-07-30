# 15 — Timeline Runtime

**Subsystem:** Event Audit & Engineering Timeline  
**Files:** `backend/routes/dashboard.py`, `storage/models.py::Event`  

---

## 1. Real-Time Telemetry

The Timeline Runtime records every milestone, task dispatch, worker status change, and code modification as a structured event.

```python
class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False) # conversation.message, task.dispatch, worker.status
    data = Column(JSON, default=dict)
    severity = Column(String, default="info") # info, warning, error
    trace_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```
