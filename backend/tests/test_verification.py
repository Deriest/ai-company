"""AIC Platform — Verification Engine Tests."""

import pytest
from verification.config import VerificationConfig, verification_config
from verification.states import VerificationState, can_transition, is_terminal, next_states, validate_state
from verification.models import VerificationReport, RequirementCheck, QualityScore


# ============================================================
# Configuration Tests
# ============================================================

class TestVerificationConfig:
    """Test verification configuration."""

    def test_default_config(self):
        config = VerificationConfig()
        assert config.enabled is True
        assert config.min_quality_score == 0.7
        assert config.enable_security_check is True

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_VERIFICATION_ENABLED", "false")
        config = VerificationConfig.from_env()
        assert config.enabled is False


# ============================================================
# State Machine Tests
# ============================================================

class TestVerificationStates:
    """Test verification state machine."""

    def test_valid_transitions(self):
        assert can_transition(VerificationState.OUTPUT_RECEIVED, VerificationState.ANALYZING_OUTPUT) is True
        assert can_transition(VerificationState.ANALYZING_OUTPUT, VerificationState.VERIFYING_REQUIREMENTS) is True
        assert can_transition(VerificationState.GENERATING_REPORT, VerificationState.VERIFICATION_COMPLETE) is True

    def test_invalid_transitions(self):
        assert can_transition(VerificationState.OUTPUT_RECEIVED, VerificationState.VERIFICATION_COMPLETE) is False

    def test_terminal_states(self):
        assert is_terminal(VerificationState.VERIFICATION_COMPLETE) is True
        assert is_terminal(VerificationState.VERIFICATION_FAILED) is True
        assert is_terminal(VerificationState.ABORTED) is True
        assert is_terminal(VerificationState.OUTPUT_RECEIVED) is False

    def test_validate_state(self):
        assert validate_state("output_received") == "output_received"
        assert validate_state("invalid") is None


# ============================================================
# Model Tests
# ============================================================

class TestVerificationModels:
    """Test verification data models."""

    def test_requirement_check(self):
        check = RequirementCheck(
            requirement_id="REQ-001",
            description="Test requirement",
            status="passed",
        )
        assert check.requirement_id == "REQ-001"
        assert check.status == "passed"

    def test_quality_score(self):
        score = QualityScore(
            code_quality=0.85,
            test_coverage=0.80,
            documentation=0.70,
            security=0.90,
            overall=0.80,
        )
        assert score.overall == 0.80

    def test_verification_report(self):
        report = VerificationReport(
            brief_id="BRIEF-TEST",
            overall_status="passed",
        )
        assert report.verification_id.startswith("VER-")
        assert report.overall_status == "passed"

    def test_verification_report_to_dict(self):
        report = VerificationReport(
            brief_id="BRIEF-TEST",
            requirements_met=[
                RequirementCheck(requirement_id="REQ-001", description="Test", status="passed"),
            ],
            quality_score=QualityScore(overall=0.85),
        )
        data = report.to_dict()
        assert "verification_id" in data
        assert "quality_score" in data


# ============================================================
# Integration Tests
# ============================================================

class TestVerificationIntegration:
    """Integration tests for verification pipeline."""

    def test_full_verification(self):
        """Test full verification pipeline."""
        # Simulate requirements
        requirements_met = [
            RequirementCheck(
                requirement_id="REQ-001",
                description="Add dark mode toggle",
                status="passed",
                evidence="Toggle implemented",
            ),
            RequirementCheck(
                requirement_id="REQ-002",
                description="Persist preference",
                status="passed",
                evidence="localStorage used",
            ),
        ]

        # Simulate acceptance criteria
        acceptance_met = [
            RequirementCheck(
                requirement_id="AC-001",
                description="Toggle works",
                status="passed",
                evidence="Tested manually",
            ),
        ]

        # Calculate quality score
        quality_score = QualityScore(
            code_quality=0.85,
            test_coverage=0.80,
            documentation=0.70,
            security=0.90,
            overall=0.80,
        )

        # Determine status
        all_passed = all(r.status == "passed" for r in requirements_met)
        all_acceptance = all(r.status == "passed" for r in acceptance_met)
        quality_ok = quality_score.overall >= 0.7

        overall_status = "passed" if all_passed and all_acceptance and quality_ok else "failed"

        # Build report
        report = VerificationReport(
            brief_id="BRIEF-TEST",
            requirements_met=requirements_met,
            acceptance_met=acceptance_met,
            quality_score=quality_score,
            overall_status=overall_status,
        )

        assert report.overall_status == "passed"
        assert len(report.requirements_met) == 2
        assert report.quality_score.overall == 0.80
