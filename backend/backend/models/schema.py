from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Provider(Base):
    __tablename__ = "providers"

    id = Column(String, primary_key=True, default=generate_uuid)
    # Round-6 FIX: unique names — POST /providers/config upserts by name while
    # POST /providers was creating duplicate rows. The unique constraint is
    # enforced for fresh DBs here and backfilled for existing DBs by migration
    # 018 (which dedupes first).
    name = Column(String, nullable=False, unique=True)
    base_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False) # Encrypted
    enabled = Column(Boolean, default=True)
    latency_ms = Column(Integer, default=0)
    status = Column(String, default="disconnected")
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ProviderModel(Base):
    __tablename__ = "provider_models"

    id = Column(String, primary_key=True, default=generate_uuid)
    provider_id = Column(String, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(String, nullable=False) # e.g. "gpt-4o"
    display_name = Column(String, nullable=False)
    owned_by = Column(String, nullable=True)

    # Capabilities (Inferred)
    context_window = Column(Integer, nullable=True)
    context_source = Column(String, nullable=True)  # "user_override", "probe", "cache", "models_dev", "catalog", "pattern", "fallback"
    context_cached_at = Column(DateTime(timezone=True), nullable=True)
    max_output_tokens = Column(Integer, nullable=True)
    supports_vision = Column(Boolean, default=False)
    supports_tool_calling = Column(Boolean, default=False)
    supports_streaming = Column(Boolean, default=True)
    supports_json_mode = Column(Boolean, default=False)
    supports_reasoning = Column(Boolean, default=False)
    supports_function_calling = Column(Boolean, default=False)
    supports_embeddings = Column(Boolean, default=False)

    raw_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

WORKER_DEFAULTS = {
    "thinker": {"label": "Thinker", "description": "Reasoning and planning specialist. Long-context analysis, strategic thinking, architecture decisions.", "system_prompt": "You are the Thinker worker in an AI engineering team. Your role is deep reasoning, strategic planning, and architectural analysis. Think step-by-step. Consider trade-offs. Provide thorough analysis before recommending actions.", "temperature": 0.2},
    "crafter": {"label": "Crafter", "description": "Code implementation and engineering specialist. Writing, refactoring, debugging code.", "system_prompt": "You are the Crafter worker in an AI engineering team. Your role is writing clean, production-quality code. Follow best practices. Write tests. Use proper error handling. Optimize for readability and maintainability.", "temperature": 0.4},
    "reviewer": {"label": "Reviewer", "description": "Code review and quality assurance specialist. Finding bugs, security issues, and improvements.", "system_prompt": "You are the Reviewer worker in an AI engineering team. Your role is thorough code review. Find bugs, security vulnerabilities, performance issues, and maintainability problems. Suggest specific improvements with code examples.", "temperature": 0.2},
    "planner": {"label": "Planner", "description": "Task planning and project architecture. Breaking down complex tasks into actionable steps.", "system_prompt": "You are the Planner worker in an AI engineering team. Your role is breaking complex tasks into clear, ordered, actionable steps. Consider dependencies. Estimate effort. Identify risks and blockers.", "temperature": 0.3},
    "manager": {"label": "Manager", "description": "Workflow orchestration and delegation. Coordinating workers and managing task flow.", "system_prompt": "You are the Manager worker in an AI engineering team. Your role is orchestrating workflows, delegating tasks to appropriate workers, and ensuring project progress. Make decisions about task routing and priorities.", "temperature": 0.4},
}

class WorkerRuntime(Base):
    __tablename__ = "worker_runtime"

    id = Column(String, primary_key=True, default=generate_uuid)
    role = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False, default="")
    description = Column(String, nullable=False, default="")
    system_prompt = Column(String, nullable=False, default="")
    provider_id = Column(String, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    model_id = Column(String, nullable=True)
    temperature = Column(Float, default=0.4)
    top_p = Column(Float, default=1.0)
    max_output_tokens = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# Merge the rest from schema.py
class Settings(Base):
    __tablename__ = "settings"

    id = Column(String, primary_key=True, default="default")
    crash_reports = Column(Boolean, default=True)
    diagnostics = Column(Boolean, default=True)
    performance = Column(Boolean, default=True)
    usage_analytics = Column(Boolean, default=False)
    session_timeout = Column(Integer, default=60)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default="default")
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    language = Column(String, default="en")
    timezone = Column(String, default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device = Column(String, nullable=False)
    location = Column(String, nullable=True)
    os = Column(String, nullable=True)
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
