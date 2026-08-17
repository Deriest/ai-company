"""PRD (Product Requirements Document) materialization.

Materializes docs/PRD.md from an EngineeringBrief into a task workspace.
This is a template-driven rendering — no LLMs involved, just data aggregation.
"""
import os
from typing import Any


def _fmt_list(items: list | None) -> str:
    if not items:
        return "- None specified"
    return "\n".join(f"- {it}" for it in items)


def brief_to_prd(brief: Any) -> str:
    """Render an EngineeringBrief object into markdown PRD content.

    The rendered PRD is a DRAFT — a template render of the raw discovery brief
    with no product judgment applied. The PM owns finalization: priorities,
    testable acceptance criteria, and resolved ambiguities.
    """

    # Title and goal
    lines = [
        "# Product Requirements Document",
        "",
        "> **Status: DRAFT** — auto-generated from the discovery brief. The PM "
        "must review and finalize this PRD (priorities, testable acceptance "
        "criteria, resolved ambiguities) before implementation.",
        "",
        "## Task Overview",
        "",
        f"**Goal:** {brief.engineering_goal or 'No goal specified'}",
        f"**Intent:** {brief.user_intent or 'No intent specified'}",
        f"**Category:** {brief.request_category}",
        "",
    ]

    # Scope
    scope = brief.scope or {}
    in_scope = scope.get("in_scope", [])
    out_of_scope = scope.get("out_of_scope", [])
    lines.extend([
        "## Scope",
        "",
        "**In Scope:**",
        _fmt_list(in_scope),
        "",
        "**Out of Scope:**",
        _fmt_list(out_of_scope),
        "",
    ])

    # Functional requirements
    lines.extend([
        "## Functional Requirements",
        "",
        _fmt_list(brief.functional_requirements or []),
        "",
    ])

    # Non-functional requirements
    lines.extend([
        "## Non-Functional Requirements",
        "",
        _fmt_list(brief.non_functional_requirements or []),
        "",
    ])

    # Constraints
    lines.extend([
        "## Constraints",
        "",
        _fmt_list(brief.constraints or []),
        "",
    ])

    # Assumptions
    lines.extend([
        "## Assumptions",
        "",
        _fmt_list(brief.assumptions or []),
        "",
    ])

    # Dependencies
    lines.extend([
        "## Dependencies",
        "",
        _fmt_list(brief.dependencies or []),
        "",
    ])

    # Risks
    lines.extend([
        "## Risks",
        "",
        _fmt_list(brief.risks or []),
        "",
    ])

    # Acceptance criteria
    lines.extend([
        "## Acceptance Criteria",
        "",
        _fmt_list(brief.acceptance_criteria or []),
        "",
    ])

    # Outstanding unknowns
    lines.extend([
        "## Outstanding Unknowns",
        "",
        _fmt_list(brief.outstanding_unknowns or []),
        "",
    ])

    # Readiness
    lines.extend([
        "## Readiness Assessment",
        "",
        f"**Status:** {brief.readiness_status.upper()}",
        f"**Score:** {brief.readiness_score:.1f}/100",
        "",
    ])

    # Metadata
    meta = brief.discovery_metadata or {}
    if meta:
        lines.append("**Discovery Metadata**")
        for k, v in meta.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    lines.append("---")
    ts = brief.updated_at.isoformat() if hasattr(brief, 'updated_at') and brief.updated_at else 'unknown date'
    lines.append(f"*Generated from Engineering Brief on {ts}*")

    return "\n".join(lines)


def materialize_prd(workspace_path: str, brief: Any) -> str | None:
    """Write docs/PRD.md to workspace_path from a brief object.

    Idempotent: if the file exists with identical content, skip the rewrite.
    Returns the path written, or None if no brief / write failed.
    """
    if brief is None:
        return None

    try:
        content = brief_to_prd(brief)
        prd_path = os.path.join(workspace_path, "docs", "PRD.md")
        prd_dir = os.path.dirname(prd_path)
        os.makedirs(prd_dir, exist_ok=True)

        # Idempotency check: skip if content is identical
        if os.path.exists(prd_path):
            with open(prd_path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return prd_path  # no change needed

        with open(prd_path, "w", encoding="utf-8") as f:
            f.write(content)
        return prd_path
    except Exception:
        return None
