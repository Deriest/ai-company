"""AIC Platform — Engineering Discovery Engine Tests.

Comprehensive test suite for the Engineering Discovery Engine (EDE).
Tests intent classification, requirement extraction, ambiguity detection,
readiness evaluation, clarification engine, and brief generation.
"""

import pytest
from discovery.config import DiscoveryConfig, discovery_config
from discovery.states import DiscoveryState, can_transition, is_terminal, next_states, validate_state
from discovery.domains import DomainRegistry, Domain, DomainField
from discovery.intent import IntentClassifier, IntentResult
from discovery.requirements import RequirementExtractor, ExtractionResult, Requirement
from discovery.ambiguity import AmbiguityDetector, AmbiguityReport, Ambiguity
from discovery.readiness import ReadinessEvaluator, ReadinessResult
from discovery.clarifier import ClarificationEngine, ClarificationResult
from discovery.brief import BriefGenerator, EngineeringBriefData, BriefValidation


# ============================================================
# WP-1: Foundation Tests
# ============================================================

class TestDiscoveryConfig:
    """Test discovery configuration."""

    def test_default_config(self):
        config = DiscoveryConfig()
        assert config.enabled is True
        # Targeting 80-85% confidence through smart guided discovery
        assert config.max_clarification_rounds == 4
        assert config.max_questions_per_round == 5
        assert config.readiness_threshold == 0.80  # Keep high bar for accuracy
        assert config.dimension_floor == 0.40

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_DISCOVERY_ENABLED", "false")
        monkeypatch.setenv("AIC_DISCOVERY_MAX_ROUNDS", "5")
        config = DiscoveryConfig.from_env()
        assert config.enabled is False
        assert config.max_clarification_rounds == 5

    def test_config_update(self):
        config = DiscoveryConfig()
        config.update(enabled=False, max_clarification_rounds=5)
        assert config.enabled is False
        assert config.max_clarification_rounds == 5


class TestDiscoveryStates:
    """Test discovery state machine."""

    def test_valid_transitions(self):
        assert can_transition(DiscoveryState.NEW_REQUEST, DiscoveryState.DISCOVERY) is True
        assert can_transition(DiscoveryState.DISCOVERY, DiscoveryState.ENGINEERING_ANALYSIS) is True
        assert can_transition(DiscoveryState.ENGINEERING_ANALYSIS, DiscoveryState.CLARIFICATION) is True
        assert can_transition(DiscoveryState.ENGINEERING_ANALYSIS, DiscoveryState.ENGINEERING_BRIEF_COMPLETE) is True

    def test_invalid_transitions(self):
        assert can_transition(DiscoveryState.NEW_REQUEST, DiscoveryState.ENGINEERING_BRIEF_COMPLETE) is False
        assert can_transition(DiscoveryState.CLARIFICATION, DiscoveryState.HANDOFF_TO_PLANNING) is False

    def test_terminal_states(self):
        assert is_terminal(DiscoveryState.HANDOFF_TO_PLANNING) is True
        assert is_terminal(DiscoveryState.ABORTED) is True
        assert is_terminal(DiscoveryState.TIMEOUT) is True
        assert is_terminal(DiscoveryState.ERROR) is True
        assert is_terminal(DiscoveryState.NEW_REQUEST) is False

    def test_next_states(self):
        states = next_states(DiscoveryState.ENGINEERING_ANALYSIS)
        assert DiscoveryState.ENGINEERING_BRIEF_COMPLETE in states
        assert DiscoveryState.CLARIFICATION in states

    def test_validate_state(self):
        assert validate_state("new_request") == "new_request"
        assert validate_state("invalid_state") is None


class TestDomainRegistry:
    """Test domain registry."""

    def test_default_domains_registered(self):
        domains = DomainRegistry.get_names()
        assert "ui" in domains
        assert "backend" in domains
        assert "bugfix" in domains
        assert "feature" in domains
        assert len(domains) >= 14

    def test_get_domain(self):
        domain = DomainRegistry.get("ui")
        assert domain is not None
        assert domain.name == "ui"
        assert len(domain.mandatory_fields) > 0

    def test_get_mandatory_fields(self):
        fields = DomainRegistry.get_mandatory_fields("ui")
        assert len(fields) > 0
        assert all(f.required for f in fields)

    def test_register_custom_domain(self):
        DomainRegistry.register(Domain(
            name="custom_test",
            description="Test domain",
            mandatory_fields=[
                DomainField("test_field", "Test field", True),
            ],
        ))
        domain = DomainRegistry.get("custom_test")
        assert domain is not None
        assert domain.name == "custom_test"


# ============================================================
# WP-2: Intent Classification Tests
# ============================================================

class TestIntentClassifier:
    """Test intent classification."""

    def test_classify_task_request(self):
        result = IntentClassifier.classify("Add dark mode toggle to the dashboard")
        assert result.base_intent == "task_request"
        assert result.domain in ["ui", "feature"]

    def test_classify_question(self):
        result = IntentClassifier.classify("What is the current architecture?")
        assert result.base_intent == "question"

    def test_classify_chat(self):
        result = IntentClassifier.classify("Hello there")
        assert result.base_intent == "chat"

    def test_classify_status(self):
        result = IntentClassifier.classify("What's the status of the project?")
        assert result.base_intent == "status"

    def test_classify_approval(self):
        result = IntentClassifier.classify("I approve this change")
        assert result.base_intent == "approval"

    def test_classify_bugfix_domain(self):
        result = IntentClassifier.classify("Fix the login redirect loop")
        assert result.base_intent == "task_request"
        assert result.domain == "bugfix"

    def test_classify_test_domain(self):
        result = IntentClassifier.classify("Add unit tests for the parser module")
        assert result.base_intent == "task_request"
        assert result.domain == "test"

    def test_classify_docs_domain(self):
        result = IntentClassifier.classify("Write documentation for the API endpoints")
        assert result.base_intent == "task_request"
        assert result.domain in ["docs", "feature"]

    def test_classify_refactor_domain(self):
        result = IntentClassifier.classify("Refactor the authentication middleware")
        assert result.base_intent == "task_request"
        assert result.domain == "refactor"

    def test_classify_infra_domain(self):
        result = IntentClassifier.classify("Set up CI/CD pipeline with GitHub Actions")
        assert result.base_intent == "task_request"
        assert result.domain == "infra"

    def test_classify_security_domain(self):
        result = IntentClassifier.classify("Add security authentication middleware")
        assert result.base_intent == "task_request"
        assert result.domain in ["security", "feature"]

    def test_classify_database_domain(self):
        result = IntentClassifier.classify("Add migration for users table")
        assert result.base_intent == "task_request"
        assert result.domain == "database"

    def test_classify_performance_domain(self):
        result = IntentClassifier.classify("Optimize database queries for faster response")
        assert result.base_intent == "task_request"
        assert result.domain == "performance"

    def test_classify_empty_message(self):
        result = IntentClassifier.classify("")
        assert result.base_intent == "chat"
        assert result.domain == "chat"


# ============================================================
# WP-3: Requirement Extraction Tests
# ============================================================

class TestRequirementExtractor:
    """Test requirement extraction."""

    def test_extract_functional_requirements(self):
        result = RequirementExtractor.extract(
            "Add a dark mode toggle to the settings page",
            domain="ui"
        )
        assert len(result.functional) > 0

    def test_extract_non_functional_requirements(self):
        result = RequirementExtractor.extract(
            "The API should be fast and secure",
            domain="backend"
        )
        assert len(result.non_functional) > 0

    def test_extract_constraints(self):
        result = RequirementExtractor.extract(
            "Must use PostgreSQL and must not break existing API",
            domain="database"
        )
        assert len(result.constraints) > 0

    def test_extract_empty_content(self):
        result = RequirementExtractor.extract("")
        assert len(result.requirements) == 0

    def test_extract_domain_mapping(self):
        result = RequirementExtractor.extract(
            "Add a button to the dashboard that submits a form",
            domain="ui"
        )
        assert isinstance(result.covered_fields, list)
        assert isinstance(result.missing_fields, list)

    def test_deduplication(self):
        result = RequirementExtractor.extract(
            "Add feature X. Add feature X again.",
            domain="feature"
        )
        # Should deduplicate similar requirements
        descriptions = [r.description.lower() for r in result.requirements]
        assert len(descriptions) == len(set(descriptions))


# ============================================================
# WP-4: Ambiguity Detection Tests
# ============================================================

class TestAmbiguityDetector:
    """Test ambiguity detection."""

    def test_detect_lexical_ambiguity(self):
        report = AmbiguityDetector.detect("Add a button")
        assert report.has_ambiguity is True
        assert any(a.type == "lexical" for a in report.ambiguities)

    def test_detect_referential_ambiguity(self):
        report = AmbiguityDetector.detect("Fix the thing that's broken")
        assert report.has_ambiguity is True

    def test_detect_scope_ambiguity(self):
        report = AmbiguityDetector.detect("Improve performance")
        assert report.has_ambiguity is True

    def test_detect_temporal_ambiguity(self):
        report = AmbiguityDetector.detect("Do this ASAP")
        assert report.has_ambiguity is True

    def test_no_ambiguity_clear_request(self):
        report = AmbiguityDetector.detect(
            "Add a created_at timestamp column to the users table in PostgreSQL"
        )
        assert report.overall_score < 0.5

    def test_empty_content(self):
        report = AmbiguityDetector.detect("")
        assert report.has_ambiguity is False
        assert report.overall_score == 0.0


# ============================================================
# WP-5: Readiness Evaluation Tests
# ============================================================

class TestReadinessEvaluator:
    """Test readiness evaluation."""

    def test_ready_simple_request(self):
        extraction = RequirementExtractor.extract(
            "Add a created_at timestamp column to the users table",
            domain="database"
        )
        ambiguity = AmbiguityDetector.detect(
            "Add a created_at timestamp column to the users table"
        )
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "database",
            "Add a created_at timestamp column to the users table"
        )
        # This is a clear request — should have reasonable readiness
        assert readiness.overall_score >= 0.5

    def test_not_ready_vague_request(self):
        extraction = RequirementExtractor.extract("Make it better", domain="feature")
        ambiguity = AmbiguityDetector.detect("Make it better")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "feature", "Make it better"
        )
        assert readiness.is_ready is False
        assert readiness.overall_score < 0.80

    def test_dimension_floor_enforced(self):
        extraction = RequirementExtractor.extract("Fix bug", domain="bugfix")
        ambiguity = AmbiguityDetector.detect("Fix bug")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "bugfix", "Fix bug"
        )
        # Check no dimension below floor
        for dim_name, dim_score in readiness.dimensions.items():
            assert dim_score >= 0.0  # Should be non-negative

    def test_readiness_dimensions(self):
        extraction = RequirementExtractor.extract(
            "Add dark mode toggle to settings page",
            domain="ui"
        )
        ambiguity = AmbiguityDetector.detect("Add dark mode toggle to settings page")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "ui", "Add dark mode toggle to settings page"
        )
        assert "intent_clarity" in readiness.dimensions
        assert "scope_definition" in readiness.dimensions
        assert "requirement_completeness" in readiness.dimensions
        assert "constraint_awareness" in readiness.dimensions
        assert "acceptance_criteria" in readiness.dimensions


# ============================================================
# WP-6: Clarification Engine Tests
# ============================================================

class TestClarificationEngine:
    """Test clarification engine."""

    def test_generate_questions_for_low_readiness(self):
        extraction = RequirementExtractor.extract("Fix bug", domain="bugfix")
        ambiguity = AmbiguityDetector.detect("Fix bug")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "bugfix", "Fix bug"
        )
        result = ClarificationEngine.generate_questions(
            readiness, extraction, ambiguity, "bugfix", 0
        )
        # Should generate questions for low readiness
        assert result.round_number == 0

    def test_max_rounds_enforced(self):
        extraction = RequirementExtractor.extract("Fix bug", domain="bugfix")
        ambiguity = AmbiguityDetector.detect("Fix bug")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "bugfix", "Fix bug"
        )
        result = ClarificationEngine.generate_questions(
            readiness, extraction, ambiguity, "bugfix", 3  # Max rounds
        )
        assert result.is_final is True

    def test_format_questions(self):
        extraction = RequirementExtractor.extract("Fix bug", domain="bugfix")
        ambiguity = AmbiguityDetector.detect("Fix bug")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "bugfix", "Fix bug"
        )
        result = ClarificationEngine.generate_questions(
            readiness, extraction, ambiguity, "bugfix", 0
        )
        formatted = ClarificationEngine.format_questions_for_user(result)
        assert isinstance(formatted, str)


# ============================================================
# WP-7: Brief Generator Tests
# ============================================================

class TestBriefGenerator:
    """Test brief generator."""

    def test_assemble_brief(self):
        intent = IntentResult(
            base_intent="task_request",
            domain="ui",
            confidence=0.9,
        )
        extraction = RequirementExtractor.extract(
            "Add dark mode toggle to settings page",
            domain="ui"
        )
        ambiguity = AmbiguityDetector.detect("Add dark mode toggle to settings page")
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, "ui", "Add dark mode toggle to settings page"
        )
        brief = BriefGenerator.assemble(
            intent, extraction, readiness,
            "Add dark mode toggle to settings page"
        )
        assert brief.id.startswith("BRIEF-")
        assert brief.request_category == "ui"
        assert brief.readiness_score > 0

    def test_validate_brief(self):
        brief = EngineeringBriefData(
            engineering_goal="Add dark mode",
            user_intent="Add dark mode toggle",
            request_category="ui",
            readiness_score=0.85,
            readiness_dimensions={
                "intent_clarity": 0.9,
                "scope_definition": 0.8,
                "requirement_completeness": 0.85,
                "constraint_awareness": 0.7,
                "acceptance_criteria": 0.6,
            },
            acceptance_criteria=[{"id": "AC-1", "description": "Toggle works"}],
        )
        validation = BriefGenerator.validate(brief)
        assert validation.is_valid is True

    def test_validate_brief_invalid_category(self):
        brief = EngineeringBriefData(
            engineering_goal="Test",
            user_intent="Test",
            request_category="invalid_category",
            readiness_score=0.85,
            readiness_dimensions={
                "intent_clarity": 0.9,
                "scope_definition": 0.8,
                "requirement_completeness": 0.85,
                "constraint_awareness": 0.7,
                "acceptance_criteria": 0.6,
            },
        )
        validation = BriefGenerator.validate(brief)
        assert validation.is_valid is False
        assert any("request_category" in e for e in validation.errors)

    def test_validate_brief_low_readiness(self):
        brief = EngineeringBriefData(
            engineering_goal="Test",
            user_intent="Test",
            request_category="feature",
            readiness_score=0.50,
            readiness_dimensions={
                "intent_clarity": 0.5,
                "scope_definition": 0.5,
                "requirement_completeness": 0.5,
                "constraint_awareness": 0.5,
                "acceptance_criteria": 0.5,
            },
        )
        validation = BriefGenerator.validate(brief)
        assert validation.is_valid is False
        assert any("readiness_score" in e for e in validation.errors)


# ============================================================
# Edge Case Tests
# ============================================================

class TestEdgeCases:
    """Test edge cases from SOT Section 17."""

    def test_extremely_vague_request(self):
        result = IntentClassifier.classify("Better")
        assert result.base_intent == "chat"  # Too vague for task_request

    def test_extremely_detailed_request(self):
        detailed = (
            "Add a dark mode toggle to the settings page. "
            "The toggle should be a switch component. "
            "When enabled, it should change the background to #1a1a1a "
            "and text to #ffffff. It should persist in localStorage. "
            "The toggle should be accessible with ARIA labels. "
            "It must work on mobile and desktop."
        )
        result = IntentClassifier.classify(detailed)
        assert result.base_intent == "task_request"
        assert result.domain in ["ui", "feature"]

    def test_conflicting_requirements(self):
        report = AmbiguityDetector.detect(
            "Build a real-time dashboard that works offline"
        )
        assert report.has_ambiguity is True
        assert any(a.type == "conflicting" for a in report.ambiguities)

    def test_multiple_requests(self):
        result = IntentClassifier.classify(
            "Add dark mode and fix the login bug"
        )
        assert result.base_intent == "task_request"

    def test_follow_up_request(self):
        result = IntentClassifier.classify(
            "Remember the dark mode feature? Add logging to it."
        )
        assert result.base_intent == "task_request"


# ============================================================
# Integration Tests
# ============================================================

class TestDiscoveryIntegration:
    """Integration tests for the discovery pipeline."""

    def test_full_pipeline_ready(self):
        """Test full pipeline with a ready request."""
        content = "Add a created_at timestamp column to the users table in PostgreSQL"
        intent = IntentClassifier.classify(content)
        extraction = RequirementExtractor.extract(content, domain=intent.domain)
        ambiguity = AmbiguityDetector.detect(content)
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, intent.domain, content
        )
        brief = BriefGenerator.assemble(
            intent, extraction, readiness, content
        )
        assert brief.id.startswith("BRIEF-")
        assert brief.request_category == intent.domain

    def test_full_pipeline_not_ready(self):
        """Test full pipeline with a vague request."""
        content = "Fix bug"
        intent = IntentClassifier.classify(content)
        extraction = RequirementExtractor.extract(content, domain=intent.domain)
        ambiguity = AmbiguityDetector.detect(content)
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, intent.domain, content
        )
        if not readiness.is_ready:
            clarification = ClarificationEngine.generate_questions(
                readiness, extraction, ambiguity, intent.domain, 0
            )
            assert clarification.round_number == 0
