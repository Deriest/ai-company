"""AIC Platform — Database Models.

All SQLAlchemy models for the platform's SQLite database.
Designed with migration path to PostgreSQL.
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey, JSON,
    Float, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid4().hex





class Base(DeclarativeBase):
    pass


class DatabaseVersion(Base):
    __tablename__ = 'db_version'
    
    version = Column(Integer, primary_key=True, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Role(str, PyEnum):
    OWNER = "owner"
    ADMIN = "admin"
    PM = "pm"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"
    WORKER = "worker"


class TaskType(str, PyEnum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    BUGHUNT = "bughunt"
    REFACTOR = "refactor"
    DOCS = "docs"
    INFRA = "infra"
    TEST = "test"
    RESEARCH = "research"


class TaskStatus(str, PyEnum):
    CREATED = "created"
    INVESTIGATE = "investigate"
    PLANNING = "planning"
    APPROVAL = "approval"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    CLOSEOUT = "closeout"
    TESTING = "testing"     # legacy alias for VERIFICATION
    REVIEW = "review"       # legacy alias for CLOSEOUT
    DOCUMENTATION = "documentation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    FAILED = "failed" 


class WorkerType(str, PyEnum):
    # Core (AIC Skill canonical)
    PM = "pm"
    ARCHITECT = "architect"
    RESEARCH = "research"
    DESIGNER = "designer"
    BACKEND = "backend"
    FRONTEND = "frontend"
    QA = "qa"
    # Extensions
    CODING = "coding"
    DATABASE = "database"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"
    DEVOPS = "devops"
    PERFORMANCE = "performance"
    DEBUGGER = "debugger"
    # Legacy aliases
    PLANNER = "planner"
    REVIEW = "review"
    TESTING = "testing" 


class WorkerStatus(str, PyEnum):
    IDLE = "idle"
    WORKING = "working"
    FAILED = "failed"
    OFFLINE = "offline"


class LeaseStatus(str, PyEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PolicyDecision(str, PyEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class EventType(str, PyEnum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    WORKER_STARTED = "worker.started"
    WORKER_COMPLETED = "worker.completed"
    WORKER_FAILED = "worker.failed"
    PHASE_ADVANCED = "phase.advanced"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    LEASE_ISSUED = "lease.issued"
    LEASE_FINISHED = "lease.finished"
    POLICY_EVALUATED = "policy.evaluated"
    CHAT_MESSAGE = "chat.message"
    SYSTEM = "system"
    # Engineering Discovery Engine events
    DISCOVERY_STARTED = "discovery.started"
    DISCOVERY_COMPLETED = "discovery.completed"
    DISCOVERY_CLARIFICATION = "discovery.clarification"
    DISCOVERY_READY = "discovery.ready"
    DISCOVERY_ABORTED = "discovery.aborted"
    DISCOVERY_TIMEOUT = "discovery.timeout"
    DISCOVERY_ERROR = "discovery.error"
    BRIEF_GENERATED = "brief.generated"
    BRIEF_VALIDATED = "brief.validated"
    BRIEF_HANDED_OFF = "brief.handed_off"


# ── Auth ───────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default=Role.VIEWER.value)
    is_active = Column(Boolean, default=True)
    api_keys = Column(JSON, default=list)  # [{key, name, created}]
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    conversations = relationship("Conversation", back_populates="user")
    approvals = relationship("Approval", back_populates="approver")


# ── Projects ───────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(128), nullable=False)
    slug = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    repo_path = Column(String(512), nullable=True)
    status = Column(String(32), default="active")
    config = Column(JSON, default=dict)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    tasks = relationship("Task", back_populates="project")
    milestones = relationship("Milestone", back_populates="project")


class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    status = Column(String(32), default="planned")  # planned, active, done
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="milestones")
    tasks = relationship("Task", back_populates="milestone")


# ── Tasks ──────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Composite index for heartbeat/staleness queries that filter by
        # status and sort/look up by started_at.
        Index("ix_task_status_started", "status", "started_at"),
    )
    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, default="")
    type = Column(String(32), nullable=False, default=TaskType.FEATURE.value)
    status = Column(String(32), nullable=False, default=TaskStatus.CREATED.value, index=True)
    priority = Column(Integer, default=0)  # 0=low, 1=med, 2=high, 3=critical
    worker_type = Column(String(32), nullable=True)
    approval_required = Column(Boolean, default=True)
    progress = Column(Integer, default=0)  # 0-100
    context = Column(JSON, default=dict)  # conversation context, intent data
    artifacts = Column(JSON, default=list)  # [{path, type, worker, timestamp}]
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_worker_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    # Decomposition: parent task links to subtasks
    parent_task_id = Column(String, ForeignKey("tasks.id"), nullable=True, index=True)
    subtask_order = Column(Integer, default=0)  # execution order within parent
    depends_on = Column(JSON, default=list)  # list of subtask IDs this depends on

    project = relationship("Project", back_populates="tasks")
    milestone = relationship("Milestone", back_populates="tasks")
    subtasks = relationship("Task", backref="parent_task", remote_side=[id], foreign_keys=[parent_task_id])
    workflow = relationship("WorkflowState", back_populates="task", uselist=False, cascade="all, delete-orphan")
    leases = relationship("Lease", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="task", cascade="all, delete-orphan")


class WorkflowState(Base):
    """FSM state for a task — tracks current phase, barrier, and history."""
    __tablename__ = "workflow_states"
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, unique=True, index=True)
    current_phase = Column(String(32), nullable=False, default=TaskStatus.CREATED.value)
    previous_phase = Column(String(32), nullable=True)
    barrier = Column(JSON, default=dict)  # {active, workers, completed, failed, startedAt, timeout}
    history = Column(JSON, default=list)  # [{phase, enteredAt, exitedAt, status}]
    recovery_attempts = Column(Integer, default=0)
    pm_review_passed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    task = relationship("Task", back_populates="workflow")


# ── Workers ────────────────────────────────────────────

class Worker(Base):
    """Registered worker instance."""
    __tablename__ = "workers"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(64), unique=True, nullable=False)
    type = Column(String(32), nullable=False)  # WorkerType
    status = Column(String(32), default=WorkerStatus.OFFLINE.value)
    capabilities = Column(JSON, default=list)  # ["coding", "debugging", "testing"]
    config = Column(JSON, default=dict)  # tier, model, timeout
    current_task_id = Column(String, nullable=True)
    current_lease_id = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Lease(Base):
    """Worker lease — authorization for a worker to execute on a task in a phase."""
    __tablename__ = "leases"
    __table_args__ = (
        # Composite index for heartbeat queries that detect stale ACTIVE leases.
        Index("ix_lease_status_created", "status", "created_at"),
        Index("ix_lease_expires", "status", "expires_at"),
    )
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    worker_id = Column(String, ForeignKey("workers.id"), nullable=False)
    worker_name = Column(String(64), nullable=False)
    worker_type = Column(String(32), nullable=False)
    phase = Column(String(32), nullable=False)
    status = Column(String(32), default=LeaseStatus.ACTIVE.value, index=True)
    artifact_path = Column(String(512), nullable=True)
    exit_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    last_heartbeat_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="leases")


# ── Conversation & Message ─────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(String, nullable=True)
    title = Column(String(256), default="New Conversation")
    context = Column(JSON, default=dict)
    folder_id = Column(String, nullable=True, index=True)
    is_archived = Column(Boolean, default=False, index=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="conversations", foreign_keys=[user_id])
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(32), nullable=True)
    meta = Column("metadata", JSON, default=dict)
    token_count = Column(Integer, nullable=True)
    model_id = Column(String, nullable=True)
    provider_id = Column(String, nullable=True)
    status = Column(String(32), default="completed")
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    # The primary API historically exposed this name while the canonical model
    # uses `meta`. Keep the public field stable without a second ORM mapper.
    @property
    def message_metadata(self):
        return self.meta

    @message_metadata.setter
    def message_metadata(self, value):
        self.meta = value


# ── Engineering Discovery Engine ────────────────────────

class DiscoverySession(Base):
    """Tracks the lifecycle of an Engineering Discovery session.

    Each task_request intent creates a DiscoverySession that progresses through
    the discovery state machine before producing an Engineering Brief.
    """
    __tablename__ = "discovery_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    # FIX (round-5): conversation_id is NOT a FK — the pipeline passes a task id
    # here (a _TaskProxy), so the FK on conversations.id was violated with FK
    # enforcement ON and stalled every batch task at the discovery stage. The
    # column is kept NOT NULL but unconstrained (it semantically references a
    # task, not a conversation).
    # FIX: Rename conversation_id to task_conversation_ref for clarity
    # This column semantically references a Task ID (for discovery sessions),
    # NOT a Conversation ID. The name was misleading and caused schema confusion.
    # Keep the column name but add explicit comment clarifying its purpose.
    task_conversation_ref = Column(String, nullable=False, index=True)  # References task.id in discovery_sessions
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="new_request", index=True)
    round_number = Column(Integer, default=0)
    questions_asked = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    context = Column(JSON, default=dict)  # extracted requirements, ambiguity, etc.
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    briefs = relationship("EngineeringBrief", back_populates="discovery_session",
                         cascade="all, delete-orphan")


class EngineeringBrief(Base):
    """Structured Engineering Brief produced by the Discovery Engine.

    The Brief is the contract between Discovery and Planning.
    It contains all information needed for the Planning Engine to begin work.
    """
    __tablename__ = "engineering_briefs"
    id = Column(String, primary_key=True, default=_uuid)
    discovery_session_id = Column(String, ForeignKey("discovery_sessions.id"),
                                  nullable=False, index=True)
    version = Column(Integer, default=1)

    # Core
    engineering_goal = Column(Text, nullable=False, default="")
    user_intent = Column(Text, nullable=False, default="")
    request_category = Column(String(32), nullable=False, default="feature")
    scope = Column(JSON, default=dict)  # {in_scope: [...], out_of_scope: [...]}

    # Requirements
    functional_requirements = Column(JSON, default=list)
    non_functional_requirements = Column(JSON, default=list)
    constraints = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)
    risks = Column(JSON, default=list)
    acceptance_criteria = Column(JSON, default=list)

    # Readiness
    readiness_status = Column(String(16), nullable=False, default="not_ready")
    readiness_score = Column(Float, nullable=False, default=0.0)
    readiness_dimensions = Column(JSON, default=dict)  # {intent_clarity: 0.8, ...}

    # Metadata
    outstanding_unknowns = Column(JSON, default=list)
    discovery_metadata = Column(JSON, default=dict)

    # Status
    status = Column(String(16), default="draft", index=True)  # draft, ready, handed_off, expired

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    discovery_session = relationship("DiscoverySession", back_populates="briefs")


# ── Planning Engine ───────────────────────────────────────

class PlanningSession(Base):
    """Tracks the lifecycle of a Planning session."""
    __tablename__ = "planning_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    brief_id = Column(String, ForeignKey("engineering_briefs.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="brief_received", index=True)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    brief = relationship("EngineeringBrief", backref="planning_sessions")


class EngineeringPlan(Base):
    """Structured Engineering Plan produced by the Planning Engine."""
    __tablename__ = "engineering_plans"
    id = Column(String, primary_key=True, default=_uuid)
    brief_id = Column(String, ForeignKey("engineering_briefs.id"), nullable=False, index=True)

    # Core
    engineering_goal = Column(Text, nullable=False, default="")
    technical_approach = Column(Text, nullable=False, default="")
    implementation_strategy = Column(String(32), nullable=False, default="hybrid")

    # Decisions and risks
    architecture_decisions = Column(JSON, default=list)
    risk_mitigations = Column(JSON, default=list)
    dependency_map = Column(JSON, default=dict)

    # Effort
    effort_estimates = Column(JSON, default=list)
    acceptance_criteria = Column(JSON, default=list)

    # Metadata
    estimated_duration = Column(String(128), default="")
    confidence_score = Column(Float, default=0.0)
    status = Column(String(16), default="draft", index=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    brief = relationship("EngineeringBrief", backref="engineering_plans")


class TaskGraphModel(Base):
    """Task Graph (DAG) produced by the Task Graph Engine."""
    __tablename__ = "task_graphs"
    id = Column(String, primary_key=True, default=_uuid)
    plan_id = Column(String, ForeignKey("engineering_plans.id"), nullable=False, index=True)

    nodes = Column(JSON, default=list)
    edges = Column(JSON, default=list)
    execution_order = Column(JSON, default=list)
    critical_path = Column(JSON, default=list)
    recovery_points = Column(JSON, default=list)

    estimated_duration = Column(String(128), default="")
    parallelism_factor = Column(Float, default=1.0)
    status = Column(String(16), default="draft", index=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    plan = relationship("EngineeringPlan", backref="task_graphs")


class DispatchSession(Base):
    """Tracks the lifecycle of a Dispatcher session."""
    __tablename__ = "dispatch_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    graph_id = Column(String, ForeignKey("task_graphs.id"), nullable=False, index=True)
    execution_log = Column(JSON, default=list)
    total_duration = Column(String(128), default="")
    success_rate = Column(Float, default=0.0)
    status = Column(String(16), default="pending", index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    graph = relationship("TaskGraphModel", backref="dispatch_sessions")


class VerificationSession(Base):
    """Tracks the lifecycle of a Verification session."""
    __tablename__ = "verification_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    brief_id = Column(String, ForeignKey("engineering_briefs.id"), nullable=False, index=True)
    requirements_met = Column(JSON, default=list)
    acceptance_met = Column(JSON, default=list)
    quality_score = Column(JSON, default=dict)
    overall_status = Column(String(16), default="pending", index=True)
    recommendations = Column(JSON, default=list)
    blocking_issues = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    brief = relationship("EngineeringBrief", backref="verification_sessions")


# ── Context & Knowledge Intelligence ─────────────────────

class KnowledgeEntry(Base):
    """Knowledge entry for Context & Knowledge Intelligence."""
    __tablename__ = "knowledge_entries"
    id = Column(String, primary_key=True, default=_uuid)
    domain = Column(String(64), nullable=False, index=True)
    key = Column(String(256), nullable=False, index=True)
    value = Column(Text, nullable=False)
    source = Column(String(128), default="")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class DecisionRecord(Base):
    """Engineering decision record."""
    __tablename__ = "decision_records"
    id = Column(String, primary_key=True, default=_uuid)
    decision = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    context = Column(Text, default="")
    outcome = Column(String(32), default="")
    created_at = Column(DateTime, default=_utcnow)


# ── Autonomous Execution Intelligence ────────────────────

class AnomalyLog(Base):
    """Anomaly detection log."""
    __tablename__ = "anomaly_log"
    id = Column(String, primary_key=True, default=_uuid)
    anomaly_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False)
    description = Column(Text, nullable=False)
    affected_component = Column(String(128), default="")
    detected_at = Column(DateTime, default=_utcnow)


class RecoveryLog(Base):
    """Recovery action log."""
    __tablename__ = "recovery_log"
    id = Column(String, primary_key=True, default=_uuid)
    anomaly_id = Column(String, ForeignKey("anomaly_log.id"), nullable=True)
    action_type = Column(String(32), nullable=False)
    success = Column(Boolean, default=False)
    details = Column(Text, default="")
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


# ── Delivery & Continuous Improvement ────────────────────

class EngineeringReport(Base):
    """Engineering delivery report."""
    __tablename__ = "engineering_reports"
    id = Column(String, primary_key=True, default=_uuid)
    brief_id = Column(String, ForeignKey("engineering_briefs.id"), nullable=True)
    plan_id = Column(String, nullable=True)
    graph_id = Column(String, nullable=True)
    verification_id = Column(String, nullable=True)
    goal = Column(Text, default="")
    outcome = Column(String(16), default="pending", index=True)
    duration = Column(String(128), default="")
    quality_score = Column(Float, default=0.0)
    total_tasks = Column(Integer, default=0)
    successful_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    lessons = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    status = Column(String(16), default="draft", index=True)
    created_at = Column(DateTime, default=_utcnow)


class LessonLearned(Base):
    """Lesson learned from execution."""
    __tablename__ = "lessons_learned"
    id = Column(String, primary_key=True, default=_uuid)
    report_id = Column(String, ForeignKey("engineering_reports.id"), nullable=True)
    lesson = Column(Text, nullable=False)
    category = Column(String(32), default="")
    impact = Column(String(16), default="medium")
    recommendation = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


# ── Approvals ──────────────────────────────────────────

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    type = Column(String(64), nullable=False)  # task_start, phase_advance, deploy
    status = Column(String(32), default=ApprovalStatus.PENDING.value, index=True)
    requested_by = Column(String(64), nullable=True)
    approver_id = Column(String, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    task = relationship("Task", back_populates="approvals")
    approver = relationship("User", back_populates="approvals")


# ── Events & Audit ─────────────────────────────────────

class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String(64), nullable=False, index=True)
    actor = Column(String(128), nullable=True)  # user:xxx, worker:xxx, system
    target = Column(String(128), nullable=True)  # task:xxx, project:xxx
    data = Column(JSON, default=dict)
    trace_id = Column(String(64), nullable=True, index=True)
    severity = Column(String(16), default="info")  # debug, info, warn, error
    created_at = Column(DateTime, default=_utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=_uuid)
    actor = Column(String(128), nullable=False)  # user:xxx, worker:xxx
    action = Column(String(128), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String, nullable=True)
    result = Column(String(16), nullable=False)  # success, denied, error
    details = Column(JSON, default=dict)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(128), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=True)
    labels = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow, index=True)


# ── LLM Providers ──────────────────────────────────────

class LLMProviderConfig(Base):
    """Persisted LLM provider configuration."""
    __tablename__ = "llm_provider_configs"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(64), unique=True, nullable=False, index=True)
    base_url = Column(String(512), nullable=False)
    api_key = Column(String(512), nullable=False, default="")  # stored encrypted in production
    models = Column(JSON, default=dict)  # {thinker: "model-id", crafter: "...", sprinter: "..."}
    is_active = Column(Boolean, default=False, index=True)
    fallback_provider = Column(String(64), nullable=True)
    timeout = Column(Integer, default=120)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class LLMUsageLog(Base):
    """Token usage log per LLM call."""
    __tablename__ = "llm_usage_logs"
    id = Column(String, primary_key=True, default=_uuid)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False)
    tier = Column(String(32), nullable=True)  # thinker, crafter, sprinter
    purpose = Column(String(64), nullable=True)  # conversation, planner, coding, review
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


# ── Durable Selective Memory ────────────────────────────

class MemoryEntry(Base):
    """Multi-scope memory entry (conversation, project, user, workspace)."""
    __tablename__ = "memory_entries"
    
    id = Column(String, primary_key=True, default=_uuid)
    scope = Column(String, nullable=False, index=True)  # session, conversation, workspace, project, user
    scope_id = Column(String, nullable=True, index=True)  # conversation_id, project_id, user_id, etc.
    key = Column(String, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    category = Column(String, nullable=True, index=True)  # fact, preference, context, summary, convention, decision
    importance = Column(Float, nullable=False, default=0.5)  # 0.0-1.0
    access_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    compressed_from = Column(JSON, nullable=True)  # list of source memory IDs if compressed
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    accessed_at = Column(DateTime, default=_utcnow)
    
    # Legacy fields for backward compatibility with project-scoped memories
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    superseded_by = Column(String, nullable=True)


# ── Automation (Event Hooks, Triggers, Notifications) ──

class EventHook(Base):
    """A registered event hook that triggers actions."""
    __tablename__ = "event_hooks"

    id = Column(String, primary_key=True, default=_uuid)
    event_type = Column(String, nullable=False, index=True)  # message.created, job.completed, etc.
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    action_type = Column(String, nullable=False)  # notify, job, webhook, script
    action_config = Column(JSON, nullable=False)  # action-specific config
    is_enabled = Column(Boolean, default=True, index=True)
    fire_count = Column(Integer, default=0)
    last_fired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Trigger(Base):
    """A condition-based trigger."""
    __tablename__ = "triggers"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    condition = Column(JSON, nullable=False)  # {"field": "...", "op": "...", "value": "..."}
    action = Column(JSON, nullable=False)  # {"type": "job|notify|hook", "config": {...}}
    is_enabled = Column(Boolean, default=True)
    fire_count = Column(Integer, default=0)
    last_fired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class Notification(Base):
    """User notification."""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    level = Column(String, nullable=False, default="info")  # info, warning, error, success
    source = Column(String, nullable=True)
    action_url = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_utcnow)


# ── RAG (Retrieval Augmented Generation) ──────────────

class Document(Base):
    """A loaded document for RAG."""
    __tablename__ = "rag_documents"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    source = Column(String, nullable=True)  # file path, URL, etc.
    content_type = Column(String, nullable=False, default="text")  # text, pdf, markdown, code
    content = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String, nullable=True)
    status = Column(String, default="loaded")  # loaded, chunking, embedding, ready, error
    error_message = Column(String, nullable=True)
    doc_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class DocumentChunk(Base):
    """A chunk of a document with embedding."""
    __tablename__ = "rag_chunks"

    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(JSON, nullable=True)  # vector as list of floats
    token_count = Column(Integer, nullable=True)
    chunk_metadata = Column(JSON, nullable=True)  # page, section, etc.
    created_at = Column(DateTime, default=_utcnow)


# ── Skill Ecosystem ─────────────────────────────────────

class SkillEntry(Base):
    """Persisted skill entry with worker assignment and toggle state."""
    __tablename__ = "skill_entries"
    id = Column(String, primary_key=True, default=_uuid)
    skill_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(64), default="general", index=True)
    source = Column(String(64), default="built-in")  # built-in | installed | custom
    instructions = Column(Text, nullable=False)
    assigned_workers = Column(JSON, default=list)  # ["backend", "frontend", "qa"]
    is_enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Plugin Ecosystem ────────────────────────────────────

class PluginEntry(Base):
    """Persisted plugin entry with worker assignment, adapter metadata, and toggle state."""
    __tablename__ = "plugin_entries"
    id = Column(String, primary_key=True, default=_uuid)
    plugin_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    version = Column(String(32), default="0.0.0")
    source = Column(String(64), default="github")  # github | local | built-in
    source_url = Column(String(512), default="")
    package_path = Column(String(512), default="")  # local path to installed package
    manifest = Column(JSON, default=dict)  # full marketplace/plugin manifest
    components = Column(JSON, default=list)  # ["skill", "scripts", "commands", "agents", "hooks", "mcp"]
    assigned_workers = Column(JSON, default=list)  # ["backend", "frontend", "qa"]
    is_enabled = Column(Boolean, default=True, index=True)
    is_required = Column(Boolean, default=False)  # worker must not run without this plugin
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Context Visibility ────────────────────────────────────

class ContextAssemblyRecord(Base):
    """Persisted context assembly for audit trail."""
    __tablename__ = "context_assemblies"
    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    query = Column(Text, nullable=False)
    sources_used = Column(JSON, default=list)  # ["memory", "rag", "knowledge"]
    chunks_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    token_budget = Column(Integer, default=4000)
    assembly_time_ms = Column(Float, default=0.0)
    extra_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow, index=True)
