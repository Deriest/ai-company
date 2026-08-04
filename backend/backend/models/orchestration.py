from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class OrchestrationSession(Base):
    """A multi-worker orchestration run."""
    __tablename__ = "orchestration_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String, nullable=False, default="sequential")  # sequential, parallel
    status = Column(String, nullable=False, default="pending", index=True)  # pending, running, paused, completed, failed, cancelled
    shared_context = Column(JSON, nullable=True)  # shared state between workers
    created_by = Column(String, nullable=True)  # worker role that created this session
    condition = Column(JSON, nullable=True)  # {"field": "...", "op": "eq|neq|gt|lt|contains", "value": "...", "then": "task_id", "else": "task_id"}
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=0)
    timeout_seconds = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrchestrationTask(Base):
    """A single task within an orchestration, assigned to a worker."""
    __tablename__ = "orchestration_tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("orchestration_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_role = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    input_context = Column(JSON, nullable=True)  # task-specific input
    output_context = Column(JSON, nullable=True)  # task result
    status = Column(String, nullable=False, default="pending", index=True)  # pending, queued, running, completed, failed, skipped, cancelled
    depends_on = Column(JSON, nullable=True)  # list of task IDs this depends on
    sequence_order = Column(Integer, nullable=False, default=0)
    condition = Column(JSON, nullable=True)  # {"field": "...", "op": "eq|neq|gt|lt|contains", "value": "...", "then": "task_id", "else": "task_id"}
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=0)
    timeout_seconds = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OrchestrationApproval(Base):
    """Approval request for a completed task."""
    __tablename__ = "orchestration_approvals"

    id = Column(String, primary_key=True, default=generate_uuid)
    task_id = Column(String, ForeignKey("orchestration_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, ForeignKey("orchestration_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected
    reason = Column(String, nullable=True)  # why approval is needed
    reviewer_notes = Column(String, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class WorkflowDefinition(Base):
    """Reusable workflow template (DAG)."""
    __tablename__ = "workflow_definitions"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    dag = Column(JSON, nullable=False)  # {"nodes": [...], "edges": [...]}
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Checkpoint(Base):
    """Execution checkpoint for workflow resume."""
    __tablename__ = "checkpoints"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("orchestration_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String, nullable=False)
    state = Column(JSON, nullable=False)  # snapshot of task state at checkpoint
    created_at = Column(DateTime(timezone=True), server_default=func.now())
