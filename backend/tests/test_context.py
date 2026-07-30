"""AIC Platform — Context & Knowledge Intelligence Tests."""

import pytest
from context.config import ContextConfig, context_config
from context.models import ProjectContext, KnowledgeEntry, DecisionRecord
from context.engine import ContextEngine


# ============================================================
# Configuration Tests
# ============================================================

class TestContextConfig:
    """Test context configuration."""

    def test_default_config(self):
        config = ContextConfig()
        assert config.enabled is True
        assert config.max_knowledge_entries == 10000
        assert config.enable_learning is True

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_CONTEXT_ENABLED", "false")
        config = ContextConfig.from_env()
        assert config.enabled is False


# ============================================================
# Model Tests
# ============================================================

class TestContextModels:
    """Test context data models."""

    def test_knowledge_entry(self):
        entry = KnowledgeEntry(
            domain="repository",
            key="main_language",
            value="Python",
        )
        assert entry.id.startswith("KNOW-")
        assert entry.domain == "repository"

    def test_decision_record(self):
        record = DecisionRecord(
            decision="Use FastAPI",
            rationale="Better async support",
        )
        assert record.id.startswith("DEC-")
        assert record.decision == "Use FastAPI"

    def test_project_context(self):
        context = ProjectContext(
            project_id="test-project",
            repository_structure={"language": "python"},
            architecture_patterns=["MVC"],
        )
        assert context.project_id == "test-project"

    def test_project_context_to_dict(self):
        context = ProjectContext(
            project_id="test-project",
            knowledge_entries=[
                KnowledgeEntry(domain="test", key="test", value="test"),
            ],
        )
        data = context.to_dict()
        assert "project_id" in data
        assert "knowledge_entries" in data


# ============================================================
# Engine Tests
# ============================================================

class TestContextEngine:
    """Test context engine."""

    @pytest.fixture
    def engine(self):
        return ContextEngine()

    async def test_add_knowledge(self, engine):
        entry = await engine.add_knowledge(
            domain="repository",
            key="main_language",
            value="Python",
        )
        assert entry.domain == "repository"
        assert entry.key == "main_language"

    async def test_get_context(self, engine):
        await engine.add_knowledge("test", "key1", "value1")
        context = await engine.get_context("test-project")
        assert context.project_id == "test-project"

    async def test_record_decision(self, engine):
        record = await engine.record_decision(
            decision="Use FastAPI",
            rationale="Better async support",
        )
        assert record.decision == "Use FastAPI"

    async def test_search_knowledge(self, engine):
        await engine.add_knowledge("test", "language", "Python")
        await engine.add_knowledge("test", "framework", "FastAPI")

        results = await engine.search_knowledge("python")
        assert len(results) >= 1

    async def test_get_stats(self, engine):
        await engine.add_knowledge("test", "key1", "value1")
        stats = engine.get_stats()
        assert stats["total_entries"] >= 1
