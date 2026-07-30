from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class MCPRegistry(Base):
    """Registered MCP server."""
    __tablename__ = "mcp_registry"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    endpoint = Column(String, nullable=False)  # MCP server URL
    protocol = Column(String, nullable=False, default="stdio")  # stdio, sse, http
    is_enabled = Column(Boolean, default=True)
    capabilities = Column(JSON, nullable=True)  # {"tools": true, "resources": true, "prompts": true}
    config = Column(JSON, nullable=True)  # server-specific config
    status = Column(String, default="disconnected")  # connected, disconnected, error
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MCPTool(Base):
    """A tool provided by an MCP server."""
    __tablename__ = "mcp_tools"

    id = Column(String, primary_key=True, default=generate_uuid)
    registry_id = Column(String, ForeignKey("mcp_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    input_schema = Column(JSON, nullable=True)  # JSON Schema for tool input
    is_enabled = Column(Boolean, default=True)
    requires_approval = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MCPToolExecution(Base):
    """Log of MCP tool executions."""
    __tablename__ = "mcp_tool_executions"

    id = Column(String, primary_key=True, default=generate_uuid)
    tool_id = Column(String, ForeignKey("mcp_tools.id", ondelete="SET NULL"), nullable=True, index=True)
    registry_id = Column(String, ForeignKey("mcp_registry.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name = Column(String, nullable=False)
    input_args = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed, denied
    error_message = Column(String, nullable=True)
    execution_time_ms = Column(Integer, default=0)
    conversation_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
