"""AIC-ADE Backend — Comprehensive Input Validation Schemas.

Pydantic models for all API endpoints.
Ensures type safety, boundary validation, and proper error responses.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Any, Dict, Union
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class TaskType(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    INFRA = "infra"
    RESEARCH = "research"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEVOPS = "devops"
    DATABASE = "database"
    UI = "ui"
    AI_LLM = "ai_llm"
    CHAT = "chat"


class ExecutionLevel(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    EXTENDED = "extended"
    FULL = "full"


class WorkerRole(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    QA = "qa"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    ARCHITECT = "architect"
    DATABASE = "database"
    DEVOPS = "devops"
    PM = "pm"
    RESEARCH = "research"
    DESIGNER = "designer"


class DiscoveryState(str, Enum):
    NEW_REQUEST = "new_request"
    DISCOVERY = "discovery"
    ENGINEERING_ANALYSIS = "engineering_analysis"
    CLARIFICATION = "clarification"
    USER_RESPONSE = "user_response"
    REQUIREMENT_UPDATE = "requirement_update"
    ENGINEERING_BRIEF_COMPLETE = "engineering_brief_complete"
    HANDOFF_TO_PLANNING = "handoff_to_planning"
    ABORTED = "aborted"
    TIMEOUT = "timeout"
    ERROR = "error"


class PlanningState(str, Enum):
    BRIEF_RECEIVED = "brief_received"
    ANALYZING = "analyzing"
    DECISION_MAKING = "decision_making"
    PLAN_DRAFTING = "plan_drafting"
    PLAN_VALIDATING = "plan_validating"
    PLAN_COMPLETE = "plan_complete"
    HANDOFF_TO_TASKGRAPH = "handoff_to_taskgraph"
    REVISING = "revising"
    ABORTED = "aborted"
    ERROR = "error"


class TaskGraphState(str, Enum):
    PLAN_RECEIVED = "plan_received"
    DECOMPOSING = "decomposing"
    ANALYZING_DEPENDENCIES = "analyzing_dependencies"
    COMPUTING_ORDER = "computing_order"
    VALIDATING_GRAPH = "validating_graph"
    GRAPH_COMPLETE = "graph_complete"
    HANDOFF_TO_DISPATCHER = "handoff_to_dispatcher"
    FIXING_CYCLES = "fixing_cycles"
    ABORTED = "aborted"
    ERROR = "error"


class DispatcherState(str, Enum):
    GRAPH_RECEIVED = "graph_received"
    SELECTING_WORKERS = "selecting_workers"
    SCHEDULING = "scheduling"
    DISPATCHING = "dispatching"
    MONITORING = "monitoring"
    COLLECTING_RESULTS = "collecting_results"
    DISPATCHER_COMPLETE = "dispatcher_complete"
    RETRYING = "retrying"
    ESCALATING = "escalating"
    DISPATCHER_FAILED = "dispatcher_failed"
    ABORTED = "aborted"
    ERROR = "error"


class VerificationState(str, Enum):
    OUTPUT_RECEIVED = "output_received"
    ANALYZING_OUTPUT = "analyzing_output"
    VERIFYING_REQUIREMENTS = "verifying_requirements"
    VALIDATING_ACCEPTANCE = "validating_acceptance"
    CHECKING_QUALITY = "checking_quality"
    VERIFYING_REGRESSION = "verifying_regression"
    REVIEWING_SECURITY = "reviewing_security"
    GENERATING_REPORT = "generating_report"
    VERIFICATION_COMPLETE = "verification_complete"
    VERIFICATION_FAILED = "verification_failed"
    ABORTED = "aborted"
    ERROR = "error"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    TIMEOUT = "timeout"
    FAILURE = "failure"
    DEADLOCK = "deadlock"
    PERFORMANCE = "performance"
    RESOURCE = "resource"


# ============================================================
# COMMON VALIDATION
# ============================================================

class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    limit: int = Field(default=50, ge=1, le=1000, description="Items per page")


class IDParam(BaseModel):
    """ID path parameter validation."""
    id: str = Field(..., min_length=1, max_length=128, description="Resource ID")


# ============================================================
# PROVIDER SCHEMAS
# ============================================================

class ProviderCreate(BaseModel):
    """Create provider request."""
    name: str = Field(..., min_length=1, max_length=128, description="Provider name")
    endpoint: str = Field(..., min_length=1, max_length=512, description="API endpoint URL")
    apiKey: Optional[str] = Field(default="", max_length=1024, description="API key")
    latencyMs: Optional[int] = Field(default=0, ge=0, le=60000, description="Latency in ms")
    version: Optional[str] = Field(default="1.0", max_length=32, description="Version")
    healthNotes: Optional[List[str]] = Field(default=[], description="Health notes")
    models: Optional[List[Any]] = Field(default=[], description="Model list")

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must start with http:// or https://')
        return v


class ProviderUpdate(BaseModel):
    """Update provider request."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    endpoint: Optional[str] = Field(default=None, min_length=1, max_length=512)
    apiKey: Optional[str] = Field(default=None, max_length=1024)
    enabled: Optional[bool] = None
    status: Optional[str] = Field(default=None, max_length=32)
    latencyMs: Optional[int] = Field(default=None, ge=0, le=60000)
    lastRefreshAt: Optional[str] = None
    modelsCachedAt: Optional[str] = None
    healthNotes: Optional[List[str]] = None
    models: Optional[List[Any]] = None

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must start with http:// or https://')
        return v


class ProviderTestRequest(BaseModel):
    """Test provider connection."""
    endpoint: str = Field(..., min_length=1, max_length=512)
    apiKey: Optional[str] = Field(default="", max_length=1024)

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must start with http:// or https://')
        return v


# ============================================================
# WORKER SCHEMAS
# ============================================================

class WorkerRuntimeUpdate(BaseModel):
    """Update worker runtime configuration."""
    providerId: Optional[str] = Field(default=None, max_length=128)
    modelId: Optional[str] = Field(default=None, max_length=128)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    topP: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    maxOutputTokens: Optional[int] = Field(default=None, ge=1, le=100000)
    systemPrompt: Optional[str] = Field(default=None, max_length=10000)
    isEnabled: Optional[bool] = None


# ============================================================
# CONVERSATION SCHEMAS
# ============================================================

class ConversationCreate(BaseModel):
    """Create conversation request."""
    title: Optional[str] = Field(default="New Conversation", max_length=512)
    project_id: Optional[str] = Field(default=None, max_length=128)
    folder_id: Optional[str] = Field(default=None, max_length=128)


class ConversationUpdate(BaseModel):
    """Update conversation request."""
    title: Optional[str] = Field(default=None, max_length=512)
    is_archived: Optional[bool] = None
    is_favorite: Optional[bool] = None
    folder_id: Optional[str] = Field(default=None, max_length=128)


class MessageCreate(BaseModel):
    """Create message request."""
    content: str = Field(..., min_length=1, max_length=100000, description="Message content")
    role: Optional[str] = Field(default="user", max_length=16)
    model_id: Optional[str] = Field(default=None, max_length=128)
    provider_id: Optional[str] = Field(default=None, max_length=128)
    attachments: Optional[List[Dict[str, Any]]] = None


class MessageUpdate(BaseModel):
    """Update message request."""
    content: Optional[str] = Field(default=None, min_length=1, max_length=100000)


class ChatRequest(BaseModel):
    """Chat request."""
    content: str = Field(..., min_length=1, max_length=100000)
    model_id: Optional[str] = Field(default=None, max_length=128)
    provider_id: Optional[str] = Field(default=None, max_length=128)
    stream: Optional[bool] = False


class ChatStreamRequest(BaseModel):
    """Chat stream request."""
    content: str = Field(..., min_length=1, max_length=100000)
    model_id: Optional[str] = Field(default=None, max_length=128)
    provider_id: Optional[str] = Field(default=None, max_length=128)


class ConversationDuplicate(BaseModel):
    """Duplicate conversation request."""
    title: Optional[str] = Field(default=None, max_length=512)


# ============================================================
# FOLDER SCHEMAS
# ============================================================

class FolderCreate(BaseModel):
    """Create folder request."""
    name: str = Field(..., min_length=1, max_length=256, description="Folder name")


# ============================================================
# SEARCH SCHEMAS
# ============================================================

class SearchRequest(BaseModel):
    """Search request."""
    q: str = Field(..., min_length=1, max_length=512, description="Search query")
    limit: Optional[int] = Field(default=50, ge=1, le=1000)


# ============================================================
# WORKER TOOL SCHEMAS
# ============================================================

class ToolExecuteRequest(BaseModel):
    """Execute tool request."""
    tool_name: str = Field(..., min_length=1, max_length=128)
    arguments: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# ORCHESTRATION SCHEMAS
# ============================================================

class OrchestrationSessionCreate(BaseModel):
    """Create orchestration session."""
    conversation_id: str = Field(..., min_length=1, max_length=128)
    mode: Optional[str] = Field(default="sequential", max_length=32)


class OrchestrationTaskCreate(BaseModel):
    """Create orchestration task."""
    worker_role: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = Field(default="", max_length=10000)
    depends_on: Optional[List[str]] = Field(default=[])


class WorkflowCreate(BaseModel):
    """Create workflow definition."""
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default="", max_length=10000)
    dag: Dict[str, Any] = Field(..., description="Workflow DAG definition")


class WorkflowInstantiate(BaseModel):
    """Instantiate a workflow."""
    conversation_id: str = Field(..., min_length=1, max_length=128)


# ============================================================
# JOB SCHEMAS
# ============================================================

class JobCreate(BaseModel):
    """Create job request."""
    name: str = Field(..., min_length=1, max_length=256)
    type: str = Field(..., min_length=1, max_length=64)
    config: Dict[str, Any] = Field(default_factory=dict)
    schedule: Optional[str] = Field(default=None, max_length=128)


class JobUpdate(BaseModel):
    """Update job request."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None


# ============================================================
# MCP SCHEMAS
# ============================================================

class MCPRegistryCreate(BaseModel):
    """Create MCP registry entry."""
    name: str = Field(..., min_length=1, max_length=256)
    type: str = Field(..., min_length=1, max_length=64)
    config: Dict[str, Any] = Field(default_factory=dict)


class MCPToolExecute(BaseModel):
    """Execute MCP tool."""
    tool_name: str = Field(..., min_length=1, max_length=256)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPApproval(BaseModel):
    """Approve MCP execution."""
    approved: bool = Field(default=False)


class MCPDiscoverTools(BaseModel):
    """Discover tools from MCP server."""
    tools: List[str] = Field(default_factory=list)


# ============================================================
# MEMORY SCHEMAS
# ============================================================

class MemoryCreate(BaseModel):
    """Create memory entry."""
    content: str = Field(..., min_length=1, max_length=100000)
    category: str = Field(default="fact", max_length=64)
    metadata: Optional[Dict[str, Any]] = None


class MemorySearch(BaseModel):
    """Search memory."""
    query: str = Field(..., min_length=1, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=64)
    limit: Optional[int] = Field(default=10, ge=1, le=100)


class MemoryCompress(BaseModel):
    """Compress memory entries."""
    scope: str = Field(..., min_length=1, max_length=64)
    scope_id: Optional[str] = Field(default=None, max_length=128)
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)


# ============================================================
# RAG SCHEMAS
# ============================================================

class RAGDocumentUpload(BaseModel):
    """Upload RAG document."""
    title: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., min_length=1, max_length=1000000)
    content_type: Optional[str] = Field(default="text", max_length=32)


class RAGContextRequest(BaseModel):
    """Request RAG context."""
    query: str = Field(..., min_length=1, max_length=1000)
    document_ids: Optional[List[str]] = None
    max_chunks: Optional[int] = Field(default=5, ge=1, le=50)


# ============================================================
# AUTOMATION SCHEMAS
# ============================================================

class AutomationTriggerCreate(BaseModel):
    """Create automation trigger."""
    name: str = Field(..., min_length=1, max_length=256)
    event_type: str = Field(..., min_length=1, max_length=128)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    action: Dict[str, Any] = Field(..., description="Action to execute")


class AutomationTriggerUpdate(BaseModel):
    """Update automation trigger."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    conditions: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


# ============================================================
# PROFILE SCHEMAS
# ============================================================

class ProfileUpdate(BaseModel):
    """Update user profile."""
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    email: Optional[str] = Field(default=None, max_length=256)
    avatar_url: Optional[str] = Field(default=None, max_length=512)


class ProfileCreate(BaseModel):
    """Create user profile."""
    display_name: str = Field(..., min_length=1, max_length=128)


# ============================================================
# DISCOVERY SCHEMAS
# ============================================================

class DiscoveryRequest(BaseModel):
    """Start discovery session."""
    content: str = Field(..., min_length=1, max_length=100000)
    conversation_id: Optional[str] = Field(default=None, max_length=128)


class ClarificationResponse(BaseModel):
    """Respond to clarification questions."""
    response: str = Field(..., min_length=1, max_length=100000)


# ============================================================
# PLANNING SCHEMAS
# ============================================================

class PlanningRequest(BaseModel):
    """Generate engineering plan."""
    brief_id: str = Field(..., min_length=1, max_length=128)
    project_context: Optional[Dict[str, Any]] = None


# ============================================================
# TASK GRAPH SCHEMAS
# ============================================================

class TaskGraphRequest(BaseModel):
    """Generate task graph."""
    plan_id: str = Field(..., min_length=1, max_length=128)


# ============================================================
# DISPATCHER SCHEMAS
# ============================================================

class DispatchRequest(BaseModel):
    """Dispatch tasks."""
    graph_id: str = Field(..., min_length=1, max_length=128)


# ============================================================
# VERIFICATION SCHEMAS
# ============================================================

class VerificationRequest(BaseModel):
    """Verify output."""
    brief_id: str = Field(..., min_length=1, max_length=128)
    task_results: Optional[Dict[str, Any]] = None


# ============================================================
# CONTEXT SCHEMAS
# ============================================================

class KnowledgeCreate(BaseModel):
    """Add knowledge entry."""
    domain: str = Field(..., min_length=1, max_length=64)
    key: str = Field(..., min_length=1, max_length=256)
    value: str = Field(..., min_length=1, max_length=100000)
    source: Optional[str] = Field(default="manual", max_length=128)


class DecisionCreate(BaseModel):
    """Record engineering decision."""
    decision: str = Field(..., min_length=1, max_length=10000)
    rationale: str = Field(..., min_length=1, max_length=10000)
    context: Optional[str] = Field(default="", max_length=10000)


class KnowledgeSearch(BaseModel):
    """Search knowledge."""
    query: str = Field(..., min_length=1, max_length=1000)
    domain: Optional[str] = Field(default=None, max_length=64)


# ============================================================
# AUTONOMY SCHEMAS
# ============================================================

class AnomalyDetect(BaseModel):
    """Detect anomaly."""
    anomaly_type: AnomalyType
    severity: Severity
    description: str = Field(..., min_length=1, max_length=10000)
    affected_component: Optional[str] = Field(default="", max_length=256)


class AnomalyHandle(BaseModel):
    """Handle anomaly."""
    anomaly_type: AnomalyType
    severity: Severity
    description: str = Field(..., min_length=1, max_length=10000)
    affected_component: Optional[str] = Field(default="", max_length=256)


# ============================================================
# DELIVERY SCHEMAS
# ============================================================

class DeliveryRequest(BaseModel):
    """Deliver engineering output."""
    brief_id: str = Field(..., min_length=1, max_length=128)
    plan_id: Optional[str] = Field(default="", max_length=128)
    graph_id: Optional[str] = Field(default="", max_length=128)
    verification_id: Optional[str] = Field(default="", max_length=128)
    task_results: Optional[Dict[str, Any]] = None


# ============================================================
# RESPONSE SCHEMAS
# ============================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    type: Optional[str] = None
    field: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: Optional[str] = None
    id: Optional[str] = None
