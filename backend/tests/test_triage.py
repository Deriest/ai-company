"""Tests for Smart Triage Engine.

Verifies:
- Classification of QUICK, STANDARD, EXTENDED, and FULL levels
- Deterministic safety guardrail enforcement
- Adversarial triage resistance
- Workforce filtering and phase skip mapping
"""
import pytest
from workflow.triage import perform_smart_triage, ExecutionLevel


def test_triage_localized_typo_quick():
    res = perform_smart_triage("Fix typo in docstring", task_type="bugfix")
    assert res.level == ExecutionLevel.QUICK
    assert "discovery" in res.skip_phases
    assert "planning" in res.skip_phases
    assert res.risk == "low"


def test_triage_calculator_module_standard():
    res = perform_smart_triage("Build a python calculator module with pytest tests", task_type="feature")
    assert res.level == ExecutionLevel.STANDARD
    assert "discovery" in res.skip_phases
    assert "designer" not in res.selected_workers


def test_triage_security_guardrail_override():
    # User asks for "quick" fix but mentions security/jwt token
    res = perform_smart_triage("Quick fix for jwt token refresh in auth header", task_type="bugfix")
    assert res.level in (ExecutionLevel.EXTENDED, ExecutionLevel.FULL)
    assert res.risk == "high"
    assert "security" in res.selected_workers
    assert len(res.guardrails_triggered) > 0


def test_triage_database_guardrail_override():
    # User asks for small change but mentions alter table / migration
    res = perform_smart_triage("Small fix: alter table users migration script", task_type="bugfix")
    assert res.level in (ExecutionLevel.EXTENDED, ExecutionLevel.FULL)
    assert res.risk == "high"
    assert "database" in res.selected_workers


def test_adversarial_triage_misleading_prompt():
    # Adversarial: prompt says "quick 1 line fix" but alters authentication architecture
    res = perform_smart_triage("Quick 1-line fix: replace authentication architecture and session tokens", task_type="bugfix")
    assert res.level == ExecutionLevel.FULL
    assert res.risk == "high"
    assert "architect" in res.selected_workers or "security" in res.selected_workers
    assert len(res.guardrails_triggered) >= 2


def test_triage_full_system_build():
    res = perform_smart_triage("Build an e-commerce app from scratch with backend and frontend", task_type="feature")
    assert res.level == ExecutionLevel.FULL
    assert len(res.skip_phases) == 0
    assert "backend" in res.selected_workers
    assert "frontend" in res.selected_workers
