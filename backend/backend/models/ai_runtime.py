from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    # Message lives in storage metadata; keep an application-level reference
    # instead of a cross-registry foreign key.
    message_id = Column(String, nullable=True, index=True)
    type = Column(String, nullable=False) # markdown, code, json, html, diff, terminal, logs, tables
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    language = Column(String, nullable=True)
    mime_type = Column(String, default="text/plain")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False, index=True)
    arguments = Column(JSON, nullable=False)
    status = Column(String, default="pending") # pending, executed, error
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ToolResult(Base):
    __tablename__ = "tool_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    tool_call_id = Column(String, ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    execution_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String, nullable=True, index=True)
    provider_id = Column(String, nullable=True)
    model_id = Column(String, nullable=True)
    latency_ms = Column(Integer, default=0)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    finish_reason = Column(String, nullable=True) # stop, length, tool_calls, error, cancelled
    status = Column(String, default="completed") # completed, error, cancelled
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class WorkerExecution(Base):
    __tablename__ = "worker_execution"

    id = Column(String, primary_key=True, default=generate_uuid)
    worker_role = Column(String, nullable=False, index=True) # thinker, crafter, reviewer, planner, manager
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String, nullable=True, index=True)
    provider_id = Column(String, nullable=True)
    model_id = Column(String, nullable=True)
    status = Column(String, default="running") # running, completed, error, cancelled
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
