"""AIC Platform — 5-Tier Adaptive Recovery Strategy Engine & PM Review Gate System.

Ported from canonical aic-skill references/recovery-strategy-engine.md & pm-review.js.
Ensures failed worker steps/phases follow an evidence-based recovery ladder up to ship_with_caveats.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("aic.recovery")


@dataclass
class RecoveryDecision:
    strategy: str  # "retry", "refine_prompt", "fallback_model", "canonical_lock", "ship_with_caveats"
    attempt: int
    feedback_prompt: str
    should_proceed: bool = True
    caveats: list[str] = field(default_factory=list)


class RecoveryEngine:
    """5-Tier Adaptive Recovery Engine for task execution & PM Review gates."""

    MAX_ATTEMPTS = 5

    def evaluate_failure(
        self,
        task_id: str,
        phase: str,
        worker_type: str,
        attempt: int,
        error_msg: str,
        previous_output: str = "",
    ) -> RecoveryDecision:
        """Determine recovery strategy based on failure attempt count and error feedback."""

        logger.info(f"Recovery Engine evaluating task {task_id[:8]} phase={phase} worker={worker_type} attempt={attempt}")

        if attempt <= 1:
            return RecoveryDecision(
                strategy="retry",
                attempt=attempt,
                feedback_prompt="Previous execution encountered a transient error. Retrying task execution.",
            )

        elif attempt == 2:
            return RecoveryDecision(
                strategy="refine_prompt",
                attempt=attempt,
                feedback_prompt=(
                    f"Previous attempt failed with error: {error_msg}.\n"
                    f"Please address the error and ensure deliverable matches specification."
                ),
            )

        elif attempt == 3:
            return RecoveryDecision(
                strategy="fallback_model",
                attempt=attempt,
                feedback_prompt=(
                    f"Multiple attempts failed. Switching to fallback LLM model tier.\n"
                    f"Error feedback: {error_msg}"
                ),
            )

        elif attempt == 4:
            return RecoveryDecision(
                strategy="canonical_lock",
                attempt=attempt,
                feedback_prompt=(
                    f"Canonical Spec Lock: Produce minimum working deliverable resolving: {error_msg}"
                ),
            )

        else:
            # Tier 5: Hard cap reached -> ship_with_caveats
            logger.warning(f"Task {task_id[:8]} reached max recovery attempts ({attempt}). Applying ship_with_caveats.")
            return RecoveryDecision(
                strategy="ship_with_caveats",
                attempt=attempt,
                feedback_prompt="Proceeding with caveats.",
                should_proceed=True,
                caveats=[f"Phase '{phase}' completed with caveats after attempt {attempt}: {error_msg}"],
            )
