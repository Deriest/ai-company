"""AIC Platform — Workflow FSM (Finite State Machine).

Enforces task lifecycle transitions by code, not by prompt.
Derived from aic-skill reference architecture with hardening:
- Strict phase validation
- Fail-closed barriers
- PM review gate
- Terminal state protection
"""
from typing import Optional
from dataclasses import dataclass, field

# ── Phase Order ────────────────────────────────────────

PHASE_ORDER = [
    "created",
    "discovery",
    "investigate",
    "planning",
    "implementation",
    "verification",
    "closeout",
    "completed",
]

TERMINAL_STATES = frozenset(["completed", "cancelled", "blocked"])

ALL_STATES = set(PHASE_ORDER) | TERMINAL_STATES

# Phases where workers execute
EXECUTION_PHASES = ["discovery", "investigate", "planning", "implementation", "verification", "closeout"]

# ── Phase → Worker mapping (aligned with AIC Skill fsm.js PHASE_PLANS) ───

PHASE_WORKERS: dict[str, list[dict]] = {
    "discovery": [
        {"worker": "hermes", "tier": "system"},
        {"worker": "pm", "tier": "thinker"},
    ],
    "investigate": [
        {"worker": "pm", "tier": "thinker"},
        {"worker": "research", "tier": "thinker"},
    ],
    "planning": [
        {"worker": "architect", "tier": "thinker"},
        {"worker": "designer", "tier": "crafter"},
        {"worker": "database", "tier": "crafter"},
        {"worker": "nexus", "tier": "crafter"},
        {"worker": "flint", "tier": "crafter"},
        {"worker": "security", "tier": "crafter"},
    ],
    "implementation": [
        {"worker": "backend", "tier": "crafter"},
        {"worker": "frontend", "tier": "crafter"},
    ],
    "verification": [
        {"worker": "qa", "tier": "sprinter"},
        {"worker": "performance", "tier": "sprinter"},
    ],
    "closeout": [
        {"worker": "rex", "tier": "sprinter"},
        {"worker": "documentation", "tier": "sprinter"},
        {"worker": "pm", "tier": "thinker"},
    ],
}

# Phases that require approval gate before advancing
APPROVAL_PHASES = frozenset(["planning"])


# ── FSM ────────────────────────────────────────────────

def normalize_phase(phase: str | None) -> str:
    return str(phase or "").lower().strip()


def validate_phase(phase: str) -> str | None:
    """Return normalized phase if valid, None if unknown."""
    p = normalize_phase(phase)
    return p if p in ALL_STATES else None


def next_phase(phase: str) -> str | None:
    """Return next phase in pipeline, or None if at end/terminal."""
    p = normalize_phase(phase)
    if p not in PHASE_ORDER:
        return None
    i = PHASE_ORDER.index(p)
    if i >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[i + 1]


def is_terminal(phase: str) -> bool:
    return normalize_phase(phase) in TERMINAL_STATES


def is_execution_phase(phase: str) -> bool:
    return normalize_phase(phase) in EXECUTION_PHASES


def can_advance(
    current_phase: str,
    barrier_complete: bool,
    pm_review_passed: bool,
    approval_passed: bool = True,
) -> bool:
    """Check if task can advance to next phase.

    Fail-closed: all conditions must be True.
    """
    if is_terminal(current_phase):
        return False

    if not barrier_complete:
        return False

    p = normalize_phase(current_phase)

    # Approval gate
    if p in APPROVAL_PHASES and not approval_passed:
        return False

    # PM review gate (required before completion from closeout)
    if p == "closeout" and not pm_review_passed:
        return False

    return next_phase(p) is not None


def _get_normal_workers_for_phase(phase: str, target_worker: str) -> list[str]:
    """Return normal (non-guardrail) workers for a phase based on target worker."""
    p = normalize_phase(phase)
    plan = PHASE_WORKERS.get(p, [])
    all_workers = [entry["worker"] for entry in plan]

    if p == "discovery":
        return ["hermes", "pm"]

    if p == "investigate":
        return ["pm", "research"]

    if p == "planning":
        if target_worker in ("frontend", "ui", "design"):
            return ["architect", "designer"]
        elif target_worker in ("backend", "database", "api"):
            return ["architect", "database"]
        elif target_worker in ("devops", "infrastructure", "flint"):
            return ["architect", "flint", "nexus"]
        elif target_worker in ("integration", "nexus", "webhook", "middleware"):
            return ["architect", "nexus"]
        elif target_worker in ("security", "sentinel"):
            return ["architect", "security"]
        return ["architect", "designer", "database"]

    if p == "implementation":
        if target_worker in ("frontend", "ui"):
            return ["frontend"]
        elif target_worker in ("backend", "api", "database"):
            return ["backend"]
        return ["backend", "frontend"]

    if p == "verification":
        return ["qa", "performance"]

    if p == "closeout":
        return ["rex", "documentation", "pm"]

    return all_workers


def allowed_workers_for_phase(
    phase: str,
    target_worker: str | None = None,
    task_type: str | None = None,
    selected_workers: list[str] | None = None,
) -> list[str]:
    """Return list of worker types allowed in a phase, dynamically filtered by task target and triage."""
    p = normalize_phase(phase)
    plan = PHASE_WORKERS.get(p, [])
    all_workers = [entry["worker"] for entry in plan]

    if not target_worker and not selected_workers:
        return all_workers

    tw = target_worker.lower() if target_worker else ""

    # BUG-12 FIX: If explicit selected_workers list is provided by triage,
    # merge guardrail-enforced workers with the normal phase workers.
    # Previously this REPLACED normal workers, causing architect/etc to be
    # skipped when security was enforced by guardrails.
    if selected_workers and p in ("implementation", "planning", "verification", "closeout"):
        phase_allowed = set(w for entry in plan for w in [entry["worker"]])
        # Guardrail workers from selected_workers that belong to this phase
        guardrail_in_phase = [w for w in selected_workers if w in phase_allowed]
        # Normal workers for this phase based on target_worker
        normal_workers = _get_normal_workers_for_phase(p, tw)
        # Merge: guardrail workers + normal workers (deduplicated, preserving order)
        merged = []
        for w in guardrail_in_phase + normal_workers:
            if w not in merged:
                merged.append(w)
        if merged:
            return merged

    if p == "discovery":
        return ["hermes", "pm"]

    if p == "investigate":
        # Research is reachable for all task types that need investigation
        if tw in ("fullstack", "architect", "pm", "coding", "research", "backend", "frontend", "database"):
            return ["pm", "research"]
        return ["pm", "research"]

    if p == "planning":
        if tw in ("frontend", "ui", "design"):
            return ["architect", "designer"]
        elif tw in ("backend", "database", "api"):
            return ["architect", "database"]
        elif tw in ("devops", "infrastructure", "flint"):
            return ["architect", "flint", "nexus"]
        elif tw in ("integration", "nexus", "webhook", "middleware"):
            return ["architect", "nexus"]
        elif tw in ("security", "sentinel"):
            return ["architect", "security"]
        return ["architect", "designer", "database"]

    if p == "implementation":
        if tw in ("frontend", "ui"):
            return ["frontend"]
        elif tw in ("backend", "api", "database"):
            return ["backend"]
        return ["backend", "frontend"]

    if p == "verification":
        return ["qa", "performance"]

    if p == "closeout":
        return ["rex", "documentation", "pm"]

    return all_workers


def validate_worker_for_phase(worker_type: str, phase: str) -> bool:
    """Check if a worker type is allowed in a phase."""
    return worker_type in allowed_workers_for_phase(phase)


# ── Barrier ────────────────────────────────────────────

@dataclass
class Barrier:
    """Phase barrier — tracks worker completion within a phase.

    Fail-closed: timed-out barriers do NOT auto-satisfy.
    """
    active: bool = True
    workers: list[str] = field(default_factory=list)
    completed: dict[str, str] = field(default_factory=dict)  # worker -> "complete"
    failed: dict[str, str] = field(default_factory=dict)  # worker -> reason
    started_at: float = 0.0  # epoch seconds
    timeout: int = 600  # seconds
    timed_out: bool = False

    def is_satisfied(self, now: float = 0.0) -> bool:
        """Check if all required workers completed. Fail-closed on timeout."""
        if not self.active:
            return False

        if now == 0.0:
            import time
            now = time.time()

        if self.started_at > 0 and (now - self.started_at) > self.timeout:
            self.active = False
            self.timed_out = True
            return False

        if not self.workers:
            return True

        return all(w in self.completed for w in self.workers)

    def mark_complete(self, worker: str) -> None:
        self.completed[worker] = "complete"

    def mark_failed(self, worker: str, reason: str = "failed") -> None:
        self.failed[worker] = reason

    def reset_for_repair(self, workers: list[str]) -> None:
        """Clear completion for workers being respawned after rework."""
        for w in workers:
            self.completed.pop(w, None)
            self.failed.pop(w, None)

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "workers": self.workers,
            "completed": self.completed,
            "failed": self.failed,
            "started_at": self.started_at,
            "timeout": self.timeout,
            "timed_out": self.timed_out,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Barrier":
        return cls(
            active=data.get("active", True),
            workers=data.get("workers", []),
            completed=data.get("completed", {}),
            failed=data.get("failed", {}),
            started_at=data.get("started_at", 0.0),
            timeout=data.get("timeout", 600),
            timed_out=data.get("timed_out", False),
        )

    @classmethod
    def start(cls, workers: list[str], timeout: int = 600) -> "Barrier":
        import time
        return cls(
            active=True,
            workers=list(set(workers)),
            started_at=time.time(),
            timeout=timeout,
        )


def clear_barrier() -> dict | None:
    return None
