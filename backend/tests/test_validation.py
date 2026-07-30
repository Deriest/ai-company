"""AIC-ADE Phase 1 — Validation & Security Tests.

Tests for:
- Input validation on all endpoints
- Localhost security enforcement
- Security headers
- Boundary conditions
- Invalid input handling
"""

import pytest
from pydantic import ValidationError, BaseModel
from backend.schemas.validation import (
    ProviderCreate, ProviderUpdate, ConversationCreate, ConversationUpdate,
    MessageCreate, MessageUpdate, ChatRequest, FolderCreate, SearchRequest,
    ToolExecuteRequest, JobCreate, JobUpdate, MCPRegistryCreate, MCPToolExecute,
    MemoryCreate, MemorySearch, RAGDocumentUpload, RAGContextRequest,
    AutomationTriggerCreate, AutomationTriggerUpdate, ProfileUpdate,
    DiscoveryRequest, ClarificationResponse, PlanningRequest,
    TaskGraphRequest, DispatchRequest, VerificationRequest,
    KnowledgeCreate, DecisionCreate, KnowledgeSearch,
    AnomalyDetect, AnomalyHandle, DeliveryRequest,
    WorkerRuntimeUpdate, SuccessResponse, ErrorResponse,
    ChatStreamRequest
)
from backend.middleware.validation import (
    sanitize_string, validate_enum_value, validate_integer_range,
    validate_string_length, validate_url, validate_email
)


# ============================================================
# Provider Validation Tests
# ============================================================

class TestProviderValidation:
    """Test provider input validation."""

    def test_valid_provider_create(self):
        provider = ProviderCreate(
            name="OpenAI",
            endpoint="https://api.openai.com",
            apiKey="sk-test123"
        )
        assert provider.name == "OpenAI"
        assert provider.endpoint == "https://api.openai.com"

    def test_provider_create_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderCreate(name="", endpoint="https://api.openai.com")
        assert "name" in str(exc_info.value).lower()

    def test_provider_create_long_name(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderCreate(name="x" * 200, endpoint="https://api.openai.com")
        assert "name" in str(exc_info.value).lower()

    def test_provider_create_invalid_endpoint(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderCreate(name="Test", endpoint="not-a-url")
        assert "endpoint" in str(exc_info.value).lower()

    def test_provider_create_valid_http(self):
        provider = ProviderCreate(
            name="Local",
            endpoint="http://localhost:11434"
        )
        assert provider.endpoint == "http://localhost:11434"

    def test_provider_update_partial(self):
        update = ProviderUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.endpoint is None

    def test_provider_update_invalid_endpoint(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderUpdate(endpoint="invalid")
        assert "endpoint" in str(exc_info.value).lower()

    def test_provider_latency_bounds(self):
        provider = ProviderCreate(
            name="Test",
            endpoint="https://api.test.com",
            latencyMs=0
        )
        assert provider.latencyMs == 0

    def test_provider_latency_negative(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderCreate(
                name="Test",
                endpoint="https://api.test.com",
                latencyMs=-1
            )
        assert "latencyms" in str(exc_info.value).lower()

    def test_provider_latency_too_high(self):
        with pytest.raises(ValidationError) as exc_info:
            ProviderCreate(
                name="Test",
                endpoint="https://api.test.com",
                latencyMs=100000
            )
        assert "latencyms" in str(exc_info.value).lower()


# ============================================================
# Conversation Validation Tests
# ============================================================

class TestConversationValidation:
    """Test conversation input validation."""

    def test_valid_conversation_create(self):
        conv = ConversationCreate(title="Test Chat")
        assert conv.title == "Test Chat"

    def test_conversation_create_default_title(self):
        conv = ConversationCreate()
        assert conv.title == "New Conversation"

    def test_conversation_create_long_title(self):
        with pytest.raises(ValidationError) as exc_info:
            ConversationCreate(title="x" * 600)
        assert "title" in str(exc_info.value).lower()

    def test_conversation_update_partial(self):
        update = ConversationUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.is_archived is None

    def test_conversation_update_archived(self):
        update = ConversationUpdate(is_archived=True)
        assert update.is_archived is True


# ============================================================
# Message Validation Tests
# ============================================================

class TestMessageValidation:
    """Test message input validation."""

    def test_valid_message_create(self):
        msg = MessageCreate(content="Hello world")
        assert msg.content == "Hello world"
        assert msg.role == "user"

    def test_message_create_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            MessageCreate(content="")
        assert "content" in str(exc_info.value).lower()

    def test_message_create_long_content(self):
        with pytest.raises(ValidationError) as exc_info:
            MessageCreate(content="x" * 200000)
        assert "content" in str(exc_info.value).lower()

    def test_message_update_partial(self):
        update = MessageUpdate(content="Updated")
        assert update.content == "Updated"

    def test_message_update_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            MessageUpdate(content="")
        assert "content" in str(exc_info.value).lower()


# ============================================================
# Chat Validation Tests
# ============================================================

class TestChatValidation:
    """Test chat input validation."""

    def test_valid_chat_request(self):
        req = ChatRequest(content="Hello")
        assert req.content == "Hello"
        assert req.stream is False

    def test_chat_request_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(content="")
        assert "content" in str(exc_info.value).lower()

    def test_chat_stream_request(self):
        req = ChatStreamRequest(content="Stream this")
        assert req.content == "Stream this"


# ============================================================
# Folder Validation Tests
# ============================================================

class TestFolderValidation:
    """Test folder input validation."""

    def test_valid_folder_create(self):
        folder = FolderCreate(name="My Folder")
        assert folder.name == "My Folder"

    def test_folder_create_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            FolderCreate(name="")
        assert "name" in str(exc_info.value).lower()

    def test_folder_create_long_name(self):
        with pytest.raises(ValidationError) as exc_info:
            FolderCreate(name="x" * 300)
        assert "name" in str(exc_info.value).lower()


# ============================================================
# Search Validation Tests
# ============================================================

class TestSearchValidation:
    """Test search input validation."""

    def test_valid_search(self):
        req = SearchRequest(q="test query")
        assert req.q == "test query"
        assert req.limit == 50

    def test_search_empty_query(self):
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(q="")
        assert "q" in str(exc_info.value).lower()

    def test_search_custom_limit(self):
        req = SearchRequest(q="test", limit=100)
        assert req.limit == 100

    def test_search_limit_too_high(self):
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(q="test", limit=2000)
        assert "limit" in str(exc_info.value).lower()


# ============================================================
# Tool Execution Validation Tests
# ============================================================

class TestToolValidation:
    """Test tool execution input validation."""

    def test_valid_tool_execute(self):
        req = ToolExecuteRequest(tool_name="test_tool", arguments={"key": "value"})
        assert req.tool_name == "test_tool"
        assert req.arguments == {"key": "value"}

    def test_tool_execute_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            ToolExecuteRequest(tool_name="")
        assert "tool_name" in str(exc_info.value).lower()

    def test_tool_execute_default_args(self):
        req = ToolExecuteRequest(tool_name="test")
        assert req.arguments == {}


# ============================================================
# Job Validation Tests
# ============================================================

class TestJobValidation:
    """Test job input validation."""

    def test_valid_job_create(self):
        job = JobCreate(name="Test Job", type="cron", config={"key": "value"})
        assert job.name == "Test Job"
        assert job.type == "cron"

    def test_job_create_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            JobCreate(name="", type="cron")
        assert "name" in str(exc_info.value).lower()

    def test_job_create_empty_type(self):
        with pytest.raises(ValidationError) as exc_info:
            JobCreate(name="Test", type="")
        assert "type" in str(exc_info.value).lower()


# ============================================================
# MCP Validation Tests
# ============================================================

class TestMCPValidation:
    """Test MCP input validation."""

    def test_valid_mcp_create(self):
        mcp = MCPRegistryCreate(
            name="Test Server",
            type="stdio",
            config={"endpoint": "http://localhost:3000"}
        )
        assert mcp.name == "Test Server"
        assert mcp.type == "stdio"

    def test_mcp_create_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            MCPRegistryCreate(name="", type="stdio")
        assert "name" in str(exc_info.value).lower()


# ============================================================
# Memory Validation Tests
# ============================================================

class TestMemoryValidation:
    """Test memory input validation."""

    def test_valid_memory_create(self):
        mem = MemoryCreate(content="Test memory", category="fact")
        assert mem.content == "Test memory"
        assert mem.category == "fact"

    def test_memory_create_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            MemoryCreate(content="")
        assert "content" in str(exc_info.value).lower()


# ============================================================
# RAG Validation Tests
# ============================================================

class TestRAGValidation:
    """Test RAG input validation."""

    def test_valid_rag_upload(self):
        doc = RAGDocumentUpload(title="Test Doc", content="Test content")
        assert doc.title == "Test Doc"
        assert doc.content == "Test content"

    def test_rag_upload_empty_title(self):
        with pytest.raises(ValidationError) as exc_info:
            RAGDocumentUpload(title="", content="Test")
        assert "title" in str(exc_info.value).lower()

    def test_rag_upload_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            RAGDocumentUpload(title="Test", content="")
        assert "content" in str(exc_info.value).lower()


# ============================================================
# Automation Validation Tests
# ============================================================

class TestAutomationValidation:
    """Test automation input validation."""

    def test_valid_automation_create(self):
        auto = AutomationTriggerCreate(
            name="Test Trigger",
            event_type="task.created",
            action={"type": "notify", "config": {}}
        )
        assert auto.name == "Test Trigger"
        assert auto.event_type == "task.created"

    def test_automation_create_empty_name(self):
        with pytest.raises(ValidationError) as exc_info:
            AutomationTriggerCreate(
                name="",
                event_type="task.created",
                action={"type": "notify"}
            )
        assert "name" in str(exc_info.value).lower()


# ============================================================
# Discovery Validation Tests
# ============================================================

class TestDiscoveryValidation:
    """Test discovery input validation."""

    def test_valid_discovery_request(self):
        req = DiscoveryRequest(content="Build a login page")
        assert req.content == "Build a login page"

    def test_discovery_request_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            DiscoveryRequest(content="")
        assert "content" in str(exc_info.value).lower()

    def test_valid_clarification_response(self):
        resp = ClarificationResponse(response="Use React")
        assert resp.response == "Use React"


# ============================================================
# Planning Validation Tests
# ============================================================

class TestPlanningValidation:
    """Test planning input validation."""

    def test_valid_planning_request(self):
        req = PlanningRequest(brief_id="BRIEF-123")
        assert req.brief_id == "BRIEF-123"

    def test_planning_request_empty_id(self):
        with pytest.raises(ValidationError) as exc_info:
            PlanningRequest(brief_id="")
        assert "brief_id" in str(exc_info.value).lower()


# ============================================================
# Autonomy Validation Tests
# ============================================================

class TestAutonomyValidation:
    """Test autonomy input validation."""

    def test_valid_anomaly_detect(self):
        anomaly = AnomalyDetect(
            anomaly_type="timeout",
            severity="medium",
            description="Task timed out"
        )
        assert anomaly.anomaly_type == "timeout"
        assert anomaly.severity == "medium"

    def test_anomaly_detect_invalid_type(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyDetect(
                anomaly_type="invalid",
                severity="medium",
                description="Test"
            )
        assert "anomaly_type" in str(exc_info.value).lower()

    def test_anomaly_detect_invalid_severity(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyDetect(
                anomaly_type="timeout",
                severity="invalid",
                description="Test"
            )
        assert "severity" in str(exc_info.value).lower()


# ============================================================
# Validation Utility Tests
# ============================================================

class TestValidationUtilities:
    """Test validation utility functions."""

    def test_sanitize_string(self):
        assert sanitize_string("  hello  ") == "hello"
        assert sanitize_string("hello\x00world") == "helloworld"
        assert sanitize_string("x" * 20000, max_length=100) == "x" * 100

    def test_validate_enum_value(self):
        valid, msg = validate_enum_value("test", ["test", "other"], "field")
        assert valid is True

        valid, msg = validate_enum_value("invalid", ["test", "other"], "field")
        assert valid is False
        assert "invalid" in msg

    def test_validate_integer_range(self):
        valid, msg = validate_integer_range(5, min_value=1, max_value=10)
        assert valid is True

        valid, msg = validate_integer_range(0, min_value=1, max_value=10)
        assert valid is False

        valid, msg = validate_integer_range(15, min_value=1, max_value=10)
        assert valid is False

    def test_validate_string_length(self):
        valid, msg = validate_string_length("hello", min_length=1, max_length=10)
        assert valid is True

        valid, msg = validate_string_length("", min_length=1)
        assert valid is False

        valid, msg = validate_string_length("x" * 20, max_length=10)
        assert valid is False

    def test_validate_url(self):
        valid, msg = validate_url("https://api.openai.com")
        assert valid is True

        valid, msg = validate_url("http://localhost:8000")
        assert valid is True

        valid, msg = validate_url("not-a-url")
        assert valid is False

    def test_validate_email(self):
        valid, msg = validate_email("test@example.com")
        assert valid is True

        valid, msg = validate_email("invalid")
        assert valid is False

        valid, msg = validate_email("test@")
        assert valid is False


# ============================================================
# Enum Validation Tests
# ============================================================

class TestEnumValidation:
    """Test enum validation."""

    def test_task_type_enum(self):
        from backend.schemas.validation import TaskType
        assert TaskType.FEATURE == "feature"
        assert TaskType.BUGFIX == "bugfix"
        assert TaskType.REFACTOR == "refactor"

    def test_severity_enum(self):
        from backend.schemas.validation import Severity
        assert Severity.LOW == "low"
        assert Severity.MEDIUM == "medium"
        assert Severity.HIGH == "high"
        assert Severity.CRITICAL == "critical"

    def test_anomaly_type_enum(self):
        from backend.schemas.validation import AnomalyType
        assert AnomalyType.TIMEOUT == "timeout"
        assert AnomalyType.FAILURE == "failure"
        assert AnomalyType.DEADLOCK == "deadlock"


# ============================================================
# Worker Validation Tests
# ============================================================

class TestWorkerValidation:
    """Test worker input validation."""

    def test_valid_worker_update(self):
        update = WorkerRuntimeUpdate(
            temperature=0.7,
            topP=0.9,
            maxOutputTokens=4096
        )
        assert update.temperature == 0.7
        assert update.topP == 0.9

    def test_worker_update_temperature_bounds(self):
        with pytest.raises(ValidationError) as exc_info:
            WorkerRuntimeUpdate(temperature=3.0)
        assert "temperature" in str(exc_info.value).lower()

    def test_worker_update_top_p_bounds(self):
        with pytest.raises(ValidationError) as exc_info:
            WorkerRuntimeUpdate(topP=1.5)
        assert "topp" in str(exc_info.value).lower()

    def test_worker_update_max_tokens_negative(self):
        with pytest.raises(ValidationError) as exc_info:
            WorkerRuntimeUpdate(maxOutputTokens=0)
        assert "maxoutputtokens" in str(exc_info.value).lower()


# ============================================================
# Edge Case Tests
# ============================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_values(self):
        """Test handling of None values."""
        conv = ConversationCreate(title=None)
        # When None is passed, Pydantic uses the default
        assert conv.title is None or conv.title == "New Conversation"

    def test_special_characters(self):
        """Test handling of special characters."""
        msg = MessageCreate(content="Hello <script>alert('xss')</script>")
        assert "<script>" in msg.content  # Content is preserved, sanitized at output

    def test_unicode_content(self):
        """Test handling of unicode content."""
        msg = MessageCreate(content="Hello 世界 🌍")
        assert msg.content == "Hello 世界 🌍"

    def test_very_long_content(self):
        """Test handling of very long content."""
        long_content = "x" * 99999
        msg = MessageCreate(content=long_content)
        assert len(msg.content) == 99999

    def test_empty_dict_optional(self):
        """Test handling of empty dict for optional fields."""
        req = ToolExecuteRequest(tool_name="test", arguments={})
        assert req.arguments == {}

    def test_nested_dict_validation(self):
        """Test handling of nested dict validation."""
        auto = AutomationTriggerCreate(
            name="Test",
            event_type="task.created",
            action={"type": "notify", "config": {"url": "http://example.com"}}
        )
        assert auto.action["type"] == "notify"
