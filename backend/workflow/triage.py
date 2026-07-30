"""AIC Platform — Smart Triage Engine.

Evaluates incoming task requests to determine:
- Intent, scope, complexity, and risk
- Execution level: L1 QUICK, L2 STANDARD, L3 EXTENDED, L4 FULL
- Minimum necessary workforce
- Risk-based verification requirements
- Deterministic safety guardrails

Integrates into canonical task creation and execution architecture.
"""
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger("aic.triage")


class ExecutionLevel(str, Enum):
    QUICK = "QUICK"         # L1: Localized, low-risk, fast path
    STANDARD = "STANDARD"   # L2: Normal scoped engineering
    EXTENDED = "EXTENDED"   # L3: Cross-component / higher-risk
    FULL = "FULL"           # L4: Full lifecycle, architecture / major build


@dataclass
class TriageResult:
    level: ExecutionLevel
    scope: str               # localized, bounded, cross_component, architecture_system
    risk: str                # low, medium, high, critical
    confidence: float        # 0.0 to 1.0
    reason: str
    guardrails_triggered: list[str] = field(default_factory=list)
    selected_workers: list[str] = field(default_factory=list)
    required_verification: list[str] = field(default_factory=list)
    skip_phases: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "scope": self.scope,
            "risk": self.risk,
            "confidence": self.confidence,
            "reason": self.reason,
            "guardrails_triggered": self.guardrails_triggered,
            "selected_workers": self.selected_workers,
            "required_verification": self.required_verification,
            "skip_phases": self.skip_phases,
        }


# Deterministic Guardrail Patterns
SECURITY_KEYWORDS = [
    "security", "auth", "oauth", "rbac", "jwt", "token", "encrypt",
    "decrypt", "hash", "password", "credential", "secret", "permission",
    "vulnerability", "injection", "xss", "csrf", "cors", "sanitize",
]
DATABASE_KEYWORDS = [
    "database", "schema", "migration", "sql", "query", "index",
    "foreign key", "constraint", "orm", "sequelize", "prisma",
]

GUARDRAIL_PATTERNS = {
    "security": {
        "pattern": r"\b(auth|authentication|password|jwt|token|secret|privilege|permission|sudo|login|oauth|security|encrypt|decrypt|hash|rbac|credential|vulnerability|injection|xss|csrf|cors|sanitize)\b",
        "min_level": ExecutionLevel.EXTENDED,
        "min_risk": "high",
        "required_worker": "security",
        "rule": "Security-sensitive keyword detected — minimum EXTENDED level required",
    },
    "database_schema": {
        "pattern": r"\b(drop table|alter table|migration|schema change|delete database|truncate|foreign key|database|schema|sql|query|index|constraint|orm|sequelize|prisma|database redesign|schema redesign)\b",
        "min_level": ExecutionLevel.EXTENDED,
        "min_risk": "high",
        "required_worker": "database",
        "rule": "Destructive database/schema change detected — minimum EXTENDED level required",
    },
    "architecture": {
        "pattern": r"\b(architecture|redesign|redesign system|microservice|rewrite core|framework migration|infrastructure|database redesign|system redesign)\b",
        "min_level": ExecutionLevel.FULL,
        "min_risk": "high",
        "required_worker": "architect",
        "rule": "System-wide architecture change detected — minimum FULL level required",
    },
}


def perform_smart_triage(
    text: str,
    task_type: str = "feature",
    worker_hint: str | None = None,
    file_count_estimate: int = 1,
) -> TriageResult:
    """Evaluate text content and context to determine optimal execution depth and workforce.

    Combines deterministic guardrails with heuristic classification.
    """
    content = text.lower()
    guardrails_triggered = []
    min_level = ExecutionLevel.QUICK
    min_risk = "low"
    enforced_workers = set()

    # 1. Evaluate Deterministic Safety Guardrails
    for gname, gcfg in GUARDRAIL_PATTERNS.items():
        if re.search(gcfg["pattern"], content):
            guardrails_triggered.append(gcfg["rule"])
            enforced_workers.add(gcfg["required_worker"])
            if _level_rank(gcfg["min_level"]) > _level_rank(min_level):
                min_level = gcfg["min_level"]
                min_risk = gcfg["min_risk"]

    # 2. Heuristic Scope & Level Assessment
    is_typo_or_tiny = bool(re.search(
        r"\b(typo|fix typo|fix spelling|rename|rename variable|small css|align button|color change|text change|fix comment|fix docstring|fix label|change label|update text|change text)\b",
        content
    ))
    is_calculator_or_isolated_module = bool(re.search(
        r"\b(standalone module|python module|utility function|calculator module|helper script|isolated function)\b",
        content
    ))
    is_bugfix_localized = bool(re.search(
        r"\b(fix bug|fix error|fix crash|fix null|fix exception|patch|repair|resolve issue)\b",
        content
    )) and not guardrails_triggered
    is_full_system_build = bool(re.search(
        r"\b(build.*app|create platform|full stack|system from scratch|new product|end-to-end|from scratch|e-commerce|complete platform|entire system|full system|complete system|build complete|build entire|complete application|entire application|full application|complete solution)\b",
        content
    ))
    is_large_scope = bool(re.search(
        r"\b(complete|entire|full)\s+(system|platform|application|solution|stack|module|service|api)\b",
        content
    ))

    calculated_level = ExecutionLevel.QUICK
    scope = "localized"
    risk = min_risk
    reason = ""

    if is_full_system_build or task_type in ("infra", "research"):
        calculated_level = ExecutionLevel.FULL
        scope = "architecture_system"
        risk = "high"
        reason = "System build or infrastructural/research task requires FULL engineering depth"

    elif is_large_scope:
        calculated_level = ExecutionLevel.FULL
        scope = "architecture_system"
        risk = "high"
        reason = "Large-scope task (complete/entire/full system) requires FULL engineering depth"

    elif is_typo_or_tiny or (is_bugfix_localized and file_count_estimate <= 2):
        calculated_level = ExecutionLevel.QUICK
        scope = "localized"
        risk = "low"
        reason = "Localized, low-risk change classified for QUICK fast-path"

    elif is_calculator_or_isolated_module or task_type == "test":
        calculated_level = ExecutionLevel.STANDARD
        scope = "bounded"
        risk = "low"
        reason = "Bounded module or test task classified for STANDARD execution"

    else:
        # Default normal scoped engineering
        calculated_level = ExecutionLevel.STANDARD
        scope = "bounded"
        risk = "medium"
        reason = "Normal scoped engineering task classified for STANDARD level"

    # 3. Apply Guardrails Override
    final_level = calculated_level
    if _level_rank(min_level) > _level_rank(calculated_level):
        final_level = min_level
        risk = min_risk
        reason = f"Overridden by safety guardrails: {'; '.join(guardrails_triggered)}"

    # 4. Workforce Selection
    selected_workers = list(enforced_workers)
    if worker_hint and worker_hint not in selected_workers:
        selected_workers.append(worker_hint)

    if final_level == ExecutionLevel.QUICK:
        if not selected_workers:
            selected_workers = ["backend"] if "backend" in content or "api" in content or "py" in content else ["frontend"]
        required_verification = ["syntax", "unit"]
        skip_phases = {
            "discovery": "Skipped in QUICK mode for localized fix",
            "investigate": "Skipped in QUICK mode for localized fix",
            "planning": "Skipped in QUICK mode — no architecture decomposition required",
            "closeout": "Auto-satisfied in QUICK mode",
        }

    elif final_level == ExecutionLevel.STANDARD:
        if not selected_workers:
            if "frontend" in content or "css" in content or "ui" in content:
                selected_workers.extend(["frontend", "qa"])
            else:
                selected_workers.extend(["backend", "qa"])
        required_verification = ["unit", "integration"]
        skip_phases = {
            "discovery": "Skipped in STANDARD mode",
            "planning": "Skipped in STANDARD mode unless subtask decomposition required",
        }

    elif final_level == ExecutionLevel.EXTENDED:
        if not selected_workers:
            selected_workers = ["backend", "frontend", "qa"]
        required_verification = ["unit", "integration", "security"]
        skip_phases = {
            "discovery": "Skipped in EXTENDED mode — proceeding directly to investigate",
        }

    else:  # FULL
        if not selected_workers:
            selected_workers = ["architect", "backend", "frontend", "qa", "documentation"]
        required_verification = ["unit", "integration", "security", "closeout_gate"]
        skip_phases = {}

    # Deduplicate selected_workers preserving order
    deduped_workers = []
    for w in selected_workers:
        if w not in deduped_workers:
            deduped_workers.append(w)

    confidence = 0.95 if guardrails_triggered else 0.85

    return TriageResult(
        level=final_level,
        scope=scope,
        risk=risk,
        confidence=confidence,
        reason=reason,
        guardrails_triggered=guardrails_triggered,
        selected_workers=deduped_workers,
        required_verification=required_verification,
        skip_phases=skip_phases,
    )


def _level_rank(level: ExecutionLevel) -> int:
    ranks = {
        ExecutionLevel.QUICK: 1,
        ExecutionLevel.STANDARD: 2,
        ExecutionLevel.EXTENDED: 3,
        ExecutionLevel.FULL: 4,
    }
    return ranks.get(level, 1)
