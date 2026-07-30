from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class Job(Base):
    """A scheduled or queued job for background execution."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    job_type = Column(String, nullable=False, index=True)  # orchestration, chat, tool, custom
    payload = Column(JSON, nullable=False)  # job-specific data
    priority = Column(Integer, nullable=False, default=5, index=True)  # 1=highest, 10=lowest
    status = Column(String, nullable=False, default="queued", index=True)  # queued, running, completed, failed, cancelled, paused
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    result = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String, ForeignKey("orchestration_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # when to run (null = immediately)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobLog(Base):
    """Structured log entries for job execution."""
    __tablename__ = "job_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String, nullable=False, default="info")  # debug, info, warn, error
    message = Column(String, nullable=False)
    log_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
