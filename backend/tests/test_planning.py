"""AIC Platform — Planning Engine Tests.

Comprehensive test suite for the Planning Engine (v2.3.3).
Tests planning states, models, analyzer, decision making, risk assessment,
effort estimation, validation, and integration.
"""

import pytest
from planning.config import PlanningConfig, planning_config
from planning.states import PlanningState, can_transition, is_terminal, next_states, validate_state
from planning.models import (
    EngineeringPlan, PlanValidation, ArchitectureDecision,
    RiskMitigation, DependencyMap, EffortEstimate, AcceptanceCriterion,
)
from planning.analyzer import BriefAnalyzer, BriefAnalysis
from planning.decision import DecisionMaker
from planning.risk import RiskAssessor
from planning.effort import EffortEstimator
from planning.validator import PlanValidator


# ============================================================
# Configuration Tests
# ============================================================

class TestPlanningConfig:
    """Test planning configuration."""

    def test_default_config(self):
        config = PlanningConfig()
        assert config.enabled is True
        assert config.max_architecture_decisions == 20
        assert config.min_confidence_score == 0.6
        assert config.require_risk_mitigation is True

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_PLANNING_ENABLED", "false")
        monkeypatch.setenv("AIC_PLANNING_MIN_CONFIDENCE", "0.8")
        config = PlanningConfig.from_env()
        assert config.enabled is False
        assert config.min_confidence_score == 0.8


# ============================================================
# State Machine Tests
# ============================================================

class TestPlanningStates:
    """Test planning state machine."""

    def test_valid_transitions(self):
        assert can_transition(PlanningState.BRIEF_RECEIVED, PlanningState.ANALYZING) is True
        assert can_transition(PlanningState.ANALYZING, PlanningState.DECISION_MAKING) is True
        assert can_transition(PlanningState.DECISION_MAKING, PlanningState.PLAN_DRAFTING) is True
        assert can_transition(PlanningState.PLAN_DRAFTING, PlanningState.PLAN_VALIDATING) is True
        assert can_transition(PlanningState.PLAN_VALIDATING, PlanningState.PLAN_COMPLETE) is True

    def test_invalid_transitions(self):
        assert can_transition(PlanningState.BRIEF_RECEIVED, PlanningState.PLAN_COMPLETE) is False
        assert can_transition(PlanningState.PLAN_COMPLETE, PlanningState.ANALYZING) is False

    def test_terminal_states(self):
        assert is_terminal(PlanningState.HANDOFF_TO_TASKGRAPH) is True
        assert is_terminal(PlanningState.ABORTED) is True
        assert is_terminal(PlanningState.ERROR) is True
        assert is_terminal(PlanningState.BRIEF_RECEIVED) is False

    def test_next_states(self):
        states = next_states(PlanningState.PLAN_VALIDATING)
        assert PlanningState.PLAN_COMPLETE in states
        assert PlanningState.REVISING in states

    def test_validate_state(self):
        assert validate_state("brief_received") == "brief_received"
        assert validate_state("invalid_state") is None


# ============================================================
# Model Tests
# ============================================================

class TestPlanningModels:
    """Test planning data models."""

    def test_engineering_plan_creation(self):
        plan = EngineeringPlan(
            engineering_goal="Add dark mode",
            technical_approach="Use CSS variables",
            implementation_strategy="hybrid",
        )
        assert plan.id.startswith("PLAN-")
        assert plan.engineering_goal == "Add dark mode"

    def test_engineering_plan_to_dict(self):
        plan = EngineeringPlan(
            engineering_goal="Test",
            technical_approach="Test",
        )
        data = plan.to_dict()
        assert "id" in data
        assert "engineering_goal" in data
        assert "implementation_strategy" in data

    def test_architecture_decision(self):
        decision = ArchitectureDecision(
            decision="Use REST API",
            rationale="Well-understood pattern",
            risk_level="low",
        )
        assert decision.decision == "Use REST API"
        assert decision.risk_level == "low"

    def test_risk_mitigation(self):
        risk = RiskMitigation(
            risk="Database migration failure",
            likelihood="medium",
            impact="high",
            mitigation="Test on copy first",
        )
        assert risk.risk == "Database migration failure"


# ============================================================
# Analyzer Tests
# ============================================================

class TestBriefAnalyzer:
    """Test brief analysis."""

    def test_analyze_simple_brief(self):
        brief_data = {
            "engineering_goal": "Fix login bug",
            "user_intent": "Users cannot login",
            "functional_requirements": [
                {"id": "REQ-001", "description": "Fix authentication error"},
            ],
        }
        analysis = BriefAnalyzer.analyze(brief_data)
        assert analysis.complexity in ["low", "medium"]
        assert analysis.scope_size in ["small", "medium"]

    def test_analyze_complex_brief(self):
        brief_data = {
            "engineering_goal": "Redesign entire authentication system",
            "user_intent": "Complete auth overhaul",
            "functional_requirements": [
                {"id": "REQ-001", "description": "Implement OAuth2"},
                {"id": "REQ-002", "description": "Add MFA support"},
                {"id": "REQ-003", "description": "Create user management API"},
                {"id": "REQ-004", "description": "Build admin dashboard"},
                {"id": "REQ-005", "description": "Add audit logging"},
            ],
        }
        analysis = BriefAnalyzer.analyze(brief_data)
        assert analysis.complexity in ["high", "very_high"]
        assert analysis.scope_size in ["medium", "large", "very_large"]

    def test_detect_technologies(self):
        brief_data = {
            "engineering_goal": "Add FastAPI endpoint with PostgreSQL",
            "user_intent": "Create new API endpoint",
        }
        analysis = BriefAnalyzer.analyze(brief_data)
        assert "python" in analysis.technology_stack or "api" in analysis.technology_stack

    def test_detect_database_changes(self):
        brief_data = {
            "engineering_goal": "Add migration for users table",
            "user_intent": "Schema change",
        }
        analysis = BriefAnalyzer.analyze(brief_data)
        assert analysis.requires_database_changes is True

    def test_detect_ui_changes(self):
        brief_data = {
            "engineering_goal": "Redesign dashboard layout",
            "user_intent": "UI changes",
        }
        analysis = BriefAnalyzer.analyze(brief_data)
        assert analysis.requires_ui_changes is True


# ============================================================
# Decision Tests
# ============================================================

class TestDecisionMaker:
    """Test decision making."""

    def test_make_decisions_with_database(self):
        analysis = BriefAnalysis(
            requires_database_changes=True,
            affected_components=["database"],
        )
        decisions = DecisionMaker.make_decisions(analysis, {})
        assert len(decisions) >= 2  # At least database + testing + error handling

    def test_make_decisions_with_api(self):
        analysis = BriefAnalysis(
            requires_api_changes=True,
            affected_components=["api"],
        )
        decisions = DecisionMaker.make_decisions(analysis, {})
        assert any("REST" in d.decision for d in decisions)

    def test_select_strategy_sequential(self):
        analysis = BriefAnalysis(
            scope_size="small",
            affected_components=["api"],
        )
        strategy = DecisionMaker.select_strategy(analysis)
        assert strategy == "sequential"

    def test_select_strategy_parallel(self):
        analysis = BriefAnalysis(
            scope_size="medium",
            affected_components=["api", "frontend", "database"],
        )
        strategy = DecisionMaker.select_strategy(analysis)
        assert strategy == "parallel"


# ============================================================
# Risk Assessment Tests
# ============================================================

class TestRiskAssessor:
    """Test risk assessment."""

    def test_assess_database_risks(self):
        analysis = BriefAnalysis(requires_database_changes=True)
        risks = RiskAssessor.assess_risks(analysis, {})
        assert any("migration" in r.risk.lower() for r in risks)

    def test_assess_api_risks(self):
        analysis = BriefAnalysis(requires_api_changes=True)
        risks = RiskAssessor.assess_risks(analysis, {})
        assert any("api" in r.risk.lower() for r in risks)

    def test_assess_ui_risks(self):
        analysis = BriefAnalysis(requires_ui_changes=True)
        risks = RiskAssessor.assess_risks(analysis, {})
        assert any("ui" in r.risk.lower() or "visual" in r.risk.lower() for r in risks)

    def test_assess_high_complexity_risks(self):
        analysis = BriefAnalysis(complexity="high")
        risks = RiskAssessor.assess_risks(analysis, {})
        assert any("performance" in r.risk.lower() for r in risks)


# ============================================================
# Effort Estimation Tests
# ============================================================

class TestEffortEstimator:
    """Test effort estimation."""

    def test_estimate_simple_requirements(self):
        analysis = BriefAnalysis(complexity="low")
        brief_data = {
            "functional_requirements": [
                {"id": "REQ-001", "description": "Fix simple bug"},
            ],
        }
        estimates = EffortEstimator.estimate_effort(analysis, brief_data)
        assert len(estimates) == 1
        assert estimates[0].complexity == "low"

    def test_estimate_complex_requirements(self):
        analysis = BriefAnalysis(complexity="high")
        brief_data = {
            "functional_requirements": [
                {"id": "REQ-001", "description": "Refactor authentication system"},
            ],
        }
        estimates = EffortEstimator.estimate_effort(analysis, brief_data)
        assert len(estimates) == 1
        assert estimates[0].complexity in ["high", "very_high"]

    def test_estimate_total_duration(self):
        estimates = [
            EffortEstimate(requirement_id="REQ-001", estimated_hours=4),
            EffortEstimate(requirement_id="REQ-002", estimated_hours=8),
        ]
        duration = EffortEstimator.estimate_total_duration(estimates)
        assert duration is not None
        assert len(duration) > 0


# ============================================================
# Validation Tests
# ============================================================

class TestPlanValidator:
    """Test plan validation."""

    def test_validate_valid_plan(self):
        plan = EngineeringPlan(
            engineering_goal="Add feature",
            technical_approach="Use component architecture",
            implementation_strategy="hybrid",
            risk_mitigations=[RiskMitigation(risk="Test risk")],
            confidence_score=0.8,
        )
        validation = PlanValidator.validate(plan)
        assert validation.is_valid is True

    def test_validate_missing_goal(self):
        plan = EngineeringPlan(
            technical_approach="Test",
            implementation_strategy="hybrid",
            risk_mitigations=[RiskMitigation(risk="Test")],
        )
        validation = PlanValidator.validate(plan)
        assert validation.is_valid is False
        assert any("engineering_goal" in e for e in validation.errors)

    def test_validate_invalid_strategy(self):
        plan = EngineeringPlan(
            engineering_goal="Test",
            technical_approach="Test",
            implementation_strategy="invalid",
            risk_mitigations=[RiskMitigation(risk="Test")],
        )
        validation = PlanValidator.validate(plan)
        assert validation.is_valid is False
        assert any("implementation_strategy" in e for e in validation.errors)

    def test_calculate_confidence(self):
        plan = EngineeringPlan(
            architecture_decisions=[
                ArchitectureDecision(decision="Test", rationale="Test", risk_level="low"),
            ],
            risk_mitigations=[
                RiskMitigation(risk="Test", likelihood="low"),
            ],
            effort_estimates=[
                EffortEstimate(requirement_id="REQ-001", confidence=0.8),
            ],
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="Test"),
            ],
        )
        confidence = PlanValidator.calculate_confidence(plan)
        assert confidence > 0.5


# ============================================================
# Integration Tests
# ============================================================

class TestPlanningIntegration:
    """Integration tests for the planning pipeline."""

    def test_full_pipeline(self):
        """Test full planning pipeline with analysis."""
        brief_data = {
            "id": "BRIEF-TEST",
            "engineering_goal": "Add dark mode toggle to settings page",
            "user_intent": "Users want dark mode",
            "functional_requirements": [
                {"id": "REQ-001", "description": "Add toggle component"},
                {"id": "REQ-002", "description": "Persist preference"},
            ],
            "acceptance_criteria": [
                {"id": "AC-001", "description": "Toggle works"},
            ],
        }

        # Analyze
        analysis = BriefAnalyzer.analyze(brief_data)
        assert analysis is not None

        # Decide
        decisions = DecisionMaker.make_decisions(analysis, brief_data)
        strategy = DecisionMaker.select_strategy(analysis)
        assert len(decisions) > 0
        assert strategy in ["sequential", "parallel", "hybrid", "incremental"]

        # Assess risks
        risks = RiskAssessor.assess_risks(analysis, brief_data)
        assert len(risks) > 0

        # Estimate effort
        estimates = EffortEstimator.estimate_effort(analysis, brief_data)
        assert len(estimates) > 0

        # Generate plan
        plan = EngineeringPlan(
            brief_id=brief_data["id"],
            engineering_goal=brief_data["engineering_goal"],
            technical_approach="Component-based UI with localStorage",
            implementation_strategy=strategy,
            architecture_decisions=decisions,
            risk_mitigations=risks,
            effort_estimates=estimates,
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="Toggle works"),
            ],
        )

        # Validate
        plan.confidence_score = PlanValidator.calculate_confidence(plan)
        validation = PlanValidator.validate(plan)
        assert validation.is_valid is True
