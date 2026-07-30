"""AIC Platform — Policy Engine.

Executable policies that decide ALLOW, DENY, or REQUIRE_APPROVAL.
No worker can bypass the dispatcher. No unauthorized action proceeds.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

from storage.models import Task, User, Role, TaskStatus, WorkerType

logger = logging.getLogger("aic.policy")


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class PolicyResult:
    decision: Decision
    reason: str = ""
    required_approvals: list[str] = None

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    @property
    def needs_approval(self) -> bool:
        return self.decision == Decision.REQUIRE_APPROVAL


# ── Policy Rules ───────────────────────────────────────

# File scope restrictions by role
FILE_SCOPE: dict[str, list[str]] = {
    "coding": ["src/**", "lib/**", "test/**", "tests/**", "package.json", "requirements.txt", "Cargo.toml"],
    "planner": [],  # planner doesn't touch files
    "review": [],   # review is read-only
    "testing": ["test/**", "tests/**", "spec/**"],
    "deployment": ["Dockerfile", "docker-compose.yml", ".env.example", "deploy/**"],
}

# Sensitive paths that always require approval
SENSITIVE_PATHS = [
    ".env", ".git/config", "docker-compose.yml", "Dockerfile",
    "package.json", "requirements.txt", "Cargo.toml",
    "*.pem", "*.key", "*.cert",
]

# Actions that always require approval
ALWAYS_APPROVAL = [
    "deploy", "release", "delete", "force_push",
    "database.migrate", "config.change",
]

# Actions that are always denied
ALWAYS_DENIED = [
    "git push --force", "git.push --force",
    "rm -rf", "drop table", "sudo ",
    "chmod 777", "| bash", "| sh", "curl | bash", "curl|bash",
]


class PolicyEngine:
    """Evaluate policies for actions."""

    def evaluate(
        self,
        action: str,
        user: User | None = None,
        task: Task | None = None,
        worker_type: str | None = None,
        resource: str | None = None,
        context: dict | None = None,
    ) -> PolicyResult:
        """Evaluate a policy for an action."""
        ctx = context or {}

        # 1. Hard denials — always blocked
        for denied in ALWAYS_DENIED:
            if denied.lower() in action.lower():
                logger.warning(f"Policy DENY: blocked action '{action}'")
                return PolicyResult(
                    decision=Decision.DENY,
                    reason=f"Action '{action}' is explicitly blocked",
                )

        # 2. Always-approval actions
        for approval_action in ALWAYS_APPROVAL:
            if approval_action in action:
                return PolicyResult(
                    decision=Decision.REQUIRE_APPROVAL,
                    reason=f"Action '{action}' requires approval",
                    required_approvals=[approval_action],
                )

        # 3. User role check
        if user:
            if not user.is_active:
                return PolicyResult(
                    decision=Decision.DENY,
                    reason="User account is inactive",
                )

            # Worker role can only execute, not manage
            if user.role == Role.WORKER.value and action.startswith(("task.create", "task.cancel", "project.")):
                return PolicyResult(
                    decision=Decision.DENY,
                    reason="Worker role cannot perform management actions",
                )

        # 4. Worker file scope check
        if worker_type and resource:
            scope = FILE_SCOPE.get(worker_type, [])
            if scope:
                allowed = any(_match_glob(resource, pattern) for pattern in scope)
                if not allowed:
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Worker '{worker_type}' cannot access '{resource}' (out of scope)",
                    )

        # 5. Sensitive path check
        if resource:
            for sensitive in SENSITIVE_PATHS:
                if _match_glob(resource, sensitive):
                    return PolicyResult(
                        decision=Decision.REQUIRE_APPROVAL,
                        reason=f"Access to sensitive path '{resource}' requires approval",
                        required_approvals=["file.sensitive"],
                    )

        # 6. Task state check — can't modify terminal tasks
        if task and task.status in ("completed", "cancelled", "blocked", "failed"):
            if action.startswith(("task.execute", "task.advance", "worker.assign")):
                return PolicyResult(
                    decision=Decision.DENY,
                    reason=f"Task is in terminal state: {task.status}",
                )

        # 7. Worker-phase validation
        if worker_type and task:
            from workflow.fsm import validate_worker_for_phase, normalize_phase
            phase = normalize_phase(task.status)
            if not validate_worker_for_phase(worker_type, phase):
                return PolicyResult(
                    decision=Decision.DENY,
                    reason=f"Worker '{worker_type}' not allowed in phase '{phase}'",
                )

        # Default: allow
        return PolicyResult(decision=Decision.ALLOW)


def _match_glob(path: str, pattern: str) -> bool:
    """Simple glob matcher supporting ** for recursive."""
    import fnmatch
    # Convert ** to fnmatch-compatible
    if "**" in pattern:
        # ponytail: simple prefix matching for ** patterns
        prefix = pattern.split("**")[0].rstrip("/")
        if path.startswith(prefix):
            suffix = pattern.split("**")[1].lstrip("/")
            if suffix:
                return path.endswith(suffix) or fnmatch.fnmatch(path, f"*{suffix}")
            return True
        return False
    return fnmatch.fnmatch(path, pattern)


# Singleton
policy = PolicyEngine()
