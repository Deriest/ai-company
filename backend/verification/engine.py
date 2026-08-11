"""Verification Engine — Core Orchestrator.

Verifies that output meets acceptance criteria and quality standards.

Primary pass/fail determination is now based on TEST_EXIT_CODE from structured
TestResult objects (PHASE 7). Pattern matching serves only as supplementary
evidence for IMPLEMENTED vs TESTED vs VERIFIED state distinctions.
"""

import logging
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import EngineeringBrief as EngineeringBriefModel
from verification.config import verification_config
from verification.states import VerificationState, can_transition
from verification.models import VerificationReport, RequirementCheck, QualityScore

logger = logging.getLogger("aic.verification")

# ---------------------------------------------------------------------------
# Patterns used for content-based quality scoring (supplementary only)
# ---------------------------------------------------------------------------
_TEST_PATTERNS = re.compile(
    r"\btest\b|\bspec\b|\.test\.|\.spec\.|describe\s*\(|it\s*\(|"
    r"def\s+test_|class\s+Test|pytest|unittest|jest\.|@Test",
    re.IGNORECASE,
)
_DOC_PATTERNS = re.compile(
    r"README|\.md\b|\bdocs?\b|/\*\*|///|//!|#\s|//\s|"
    r"@param|@returns?|@description|docstring|\"\"\"",
    re.IGNORECASE,
)
_SECURITY_PATTERNS = re.compile(
    r"\bauth(enticate|orization|or)?\b|\bvalidat(ion|e|or)\b|"
    r"\bsanitiz(e|ation)\b|\bencrypt(ion|ed|er)?\b|"
    r"\bhash\b|\btoken\b|\bcsrf\b|\bxss\b|\bsec(ure|urity)\b|"
    r"\bpermissions?\b|\bac(cess|l)\b|\brbac\b",
    re.IGNORECASE,
)
_REGRESSION_NEGATIVE_PATTERNS = re.compile(
    r"\b(broken|regress|fail(ed|ure)?|error|exception|traceback|"
    r"backward.?compat|breaking.?change|deprecated)\b",
    re.IGNORECASE,
)

# Words too generic to be useful for requirement keyword matching
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "of", "in", "to",
    "for", "with", "on", "at", "by", "from", "as", "into", "through",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "because", "if", "when", "while", "that",
    "this", "it", "its", "he", "she", "they", "them", "we", "us",
    "i", "me", "my", "your", "our", "their", "about", "up", "out",
    "then", "also", "able", "need", "use", "used", "using", "one",
    "two", "new", "based", "system", "feature", "functionality",
    "should", "must", "shall", "able", "allow", "support", "provide",
})


class VerificationResult:
    """Result of verification operation."""

    def __init__(
        self,
        state: str,
        report: VerificationReport | None = None,
        message: str = "",
        metadata: dict | None = None,
    ):
        self.state = state
        self.report = report
        self.message = message
        self.metadata = metadata or {}


class VerificationEngine:
    """Verification Engine — verifies output quality."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._current_state: str | None = None

    # ------------------------------------------------------------------
    # State machine helpers
    # ------------------------------------------------------------------

    def _transition_state(self, new_state: VerificationState) -> None:
        """Transition to *new_state*, validating the move when possible."""
        new_value = new_state.value
        if self._current_state is not None and not can_transition(self._current_state, new_value):
            logger.warning(
                "Invalid state transition %s → %s (forcing anyway)",
                self._current_state,
                new_value,
            )
        prev = self._current_state
        self._current_state = new_value
        logger.debug("State: %s → %s", prev, new_value)

    # ------------------------------------------------------------------
    # Text extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_task_text(task_result: dict) -> str:
        """Pull all meaningful text out of a single task result dict."""
        parts: list[str] = []
        for key in ("output", "result", "content", "summary", "description",
                     "code", "text", "body", "message", "log", "details"):
            val = task_result.get(key)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(item) for item in val)
            elif isinstance(val, dict):
                parts.append(VerificationEngine._extract_task_text(val))
        # Also include file paths / names if present
        for key in ("files", "file_path", "path", "paths"):
            val = task_result.get(key)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(item) for item in val)
        return "\n".join(parts)

    @staticmethod
    def _extract_all_text(task_results: dict) -> str:
        """Concatenate text from *all* task results into one corpus."""
        chunks: list[str] = []
        for node_id, task_result in task_results.items():
            if isinstance(task_result, dict):
                chunks.append(VerificationEngine._extract_task_text(task_result))
            elif isinstance(task_result, str):
                chunks.append(task_result)
        return "\n".join(chunks)

    # ------------------------------------------------------------------
    # Keyword extraction for requirements traceability
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Return meaningful lower-case keywords from *text*."""
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())
        return [w for w in words if w not in _STOP_WORDS]

    @staticmethod
    def _keyword_match(keywords: list[str], corpus: str) -> tuple[int, list[str]]:
        """Return (match_count, matched_keywords) for *keywords* in *corpus*."""
        corpus_lower = corpus.lower()
        matched: list[str] = []
        for kw in keywords:
            if kw in corpus_lower:
                matched.append(kw)
        return len(matched), matched

    # ------------------------------------------------------------------
    # Quality scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_test_coverage(task_results: dict) -> float:
        """Score test coverage by inspecting task outputs for test content."""
        if not task_results:
            return 0.0
        total = 0
        hits = 0
        for task_result in task_results.values():
            if isinstance(task_result, dict):
                text = VerificationEngine._extract_task_text(task_result)
            elif isinstance(task_result, str):
                text = task_result
            else:
                continue
            total += 1
            if _TEST_PATTERNS.search(text):
                hits += 1
        return hits / total if total > 0 else 0.0

    @staticmethod
    def _score_documentation(task_results: dict) -> float:
        """Score documentation by inspecting task outputs for doc markers."""
        if not task_results:
            return 0.0
        total = 0
        hits = 0
        for task_result in task_results.values():
            if isinstance(task_result, dict):
                text = VerificationEngine._extract_task_text(task_result)
            elif isinstance(task_result, str):
                text = task_result
            else:
                continue
            total += 1
            if _DOC_PATTERNS.search(text):
                hits += 1
        return hits / total if total > 0 else 0.0

    @staticmethod
    def _score_security(task_results: dict) -> float:
        """Score security by inspecting task outputs for security patterns."""
        if not task_results:
            return 0.0
        total = 0
        hits = 0
        for task_result in task_results.values():
            if isinstance(task_result, dict):
                text = VerificationEngine._extract_task_text(task_result)
            elif isinstance(task_result, str):
                text = task_result
            else:
                continue
            total += 1
            if _SECURITY_PATTERNS.search(text):
                hits += 1
        return hits / total if total > 0 else 0.0

    @staticmethod
    def _compute_regression_results(task_results: dict) -> list[dict]:
        """Scan task outputs for signs of regressions or breaking changes."""
        findings: list[dict] = []
        for node_id, task_result in task_results.items():
            if isinstance(task_result, dict):
                text = VerificationEngine._extract_task_text(task_result)
            elif isinstance(task_result, str):
                text = task_result
            else:
                continue
            match = _REGRESSION_NEGATIVE_PATTERNS.search(text)
            if match:
                findings.append({
                    "node_id": node_id,
                    "issue": f"Potential regression indicator: '{match.group()}'",
                    "severity": "warning",
                })
        return findings

    @staticmethod
    def _compute_security_findings(task_results: dict) -> list[dict]:
        """Scan task outputs for security-related observations."""
        findings: list[dict] = []
        for node_id, task_result in task_results.items():
            if isinstance(task_result, dict):
                text = VerificationEngine._extract_task_text(task_result)
            elif isinstance(task_result, str):
                text = task_result
            else:
                continue
            matches = _SECURITY_PATTERNS.findall(text)
            if matches:
                unique = sorted(set(m.lower() for m in matches))
                findings.append({
                    "node_id": node_id,
                    "patterns_found": unique,
                    "severity": "info",
                    "detail": f"Security-related patterns detected: {', '.join(unique)}",
                })
        return findings

    # ------------------------------------------------------------------
    # Main verification entry-point
    # ------------------------------------------------------------------

    async def verify(
        self,
        brief_id: str,
        task_results: dict | None = None,
        test_results: list | None = None,  # Optional structured TestResult objects from test_runner
    ) -> VerificationResult:
        """Verify output against acceptance criteria.

        Primary pass/fail is determined by TEST_EXIT_CODE (if test_results provided).
        Pattern matching serves only as supplementary evidence.

        Walks the full state machine:
            OUTPUT_RECEIVED → ANALYZING_OUTPUT → VERIFYING_REQUIREMENTS →
            VALIDATING_ACCEPTANCE → CHECKING_QUALITY → VERIFYING_REGRESSION →
            REVIEWING_SECURITY → GENERATING_REPORT → (COMPLETE | FAILED)

        Args:
            brief_id: Engineering Brief ID
            task_results: Results from dispatcher
            test_results: Optional structured TestResult objects from test_runner

        Returns:
            VerificationResult with report
        """
        if not verification_config.enabled:
            return VerificationResult(
                state="disabled",
                message="Verification is disabled",
            )

        task_results = task_results or {}
        
        # Process structured test results from test_runner (PHASE 7)
        test_results_processed = []
        test_exit_code = -1
        test_coverage_verified = False
        
        if test_results:
            for tr in test_results:
                if hasattr(tr, '__dict__'):
                    # TestResult object
                    test_results_processed.append({
                        "language": tr.language,
                        "framework": tr.framework,
                        "exit_code": getattr(tr, "exit_code", -1),
                        "duration": getattr(tr, "duration", 0.0),
                        "summary": getattr(tr, "summary", ""),
                    })
                    test_exit_code = getattr(tr, "exit_code", -1)
                    if test_exit_code == 0:
                        test_coverage_verified = True
                elif isinstance(tr, dict):
                    test_results_processed.append(tr)
                    if tr.get("exit_code") == 0:
                        test_exit_code = 0
                        test_coverage_verified = True
                elif tr == 0:
                    test_exit_code = 0
                    test_coverage_verified = True
                    test_results_processed.append({"exit_code": 0, "summary": "Tests passed"})

        logger.info(f"Test execution: exit_code={test_exit_code}, verified={test_coverage_verified}")

        # ── STATE 1: OUTPUT_RECEIVED ────────────────────────────────
        self._transition_state(VerificationState.OUTPUT_RECEIVED)

        # Load brief
        result = await self.session.execute(
            select(EngineeringBriefModel).where(EngineeringBriefModel.id == brief_id)
        )
        brief_model = result.scalar_one_or_none()

        if not brief_model:
            self._transition_state(VerificationState.ERROR)
            return VerificationResult(
                state=self._current_state,
                message=f"Brief not found: {brief_id}",
            )

        acceptance_criteria = brief_model.acceptance_criteria or []
        functional_requirements = brief_model.functional_requirements or []

        # ── STATE 2: ANALYZING_OUTPUT ───────────────────────────────
        self._transition_state(VerificationState.ANALYZING_OUTPUT)

        corpus = self._extract_all_text(task_results)
        total_tasks = len(task_results)
        completed_tasks = sum(
            1 for r in task_results.values()
            if isinstance(r, dict) and r.get("status") == "completed"
        )
        logger.info(
            "Analyzing %d task results (%d completed), corpus length=%d",
            total_tasks, completed_tasks, len(corpus),
        )

        # ── STATE 3: VERIFYING_REQUIREMENTS ─────────────────────────
        self._transition_state(VerificationState.VERIFYING_REQUIREMENTS)

        requirements_met: list[RequirementCheck] = []
        for req in functional_requirements:
            if not isinstance(req, dict):
                continue

            req_id = req.get("id", "REQ-???")
            description = req.get("description", "")

            if not task_results or not corpus.strip():
                requirements_met.append(RequirementCheck(
                    requirement_id=req_id,
                    description=description,
                    status="failed",
                    evidence="No task results provided",
                ))
                continue

            # Extract meaningful keywords from the requirement description
            keywords = self._extract_keywords(description)

            if not keywords:
                # Description is too generic — mark as passed if any task completed
                if completed_tasks > 0:
                    requirements_met.append(RequirementCheck(
                        requirement_id=req_id,
                        description=description,
                        status="passed",
                        evidence=f"{completed_tasks} task(s) completed; requirement too generic for keyword check",
                    ))
                else:
                    requirements_met.append(RequirementCheck(
                        requirement_id=req_id,
                        description=description,
                        status="failed",
                        evidence="No tasks completed and requirement too generic for keyword check",
                    ))
                continue

            # Search per-task so we can identify *which* task addressed it
            best_match_count = 0
            best_matched: list[str] = []
            best_node: str = ""

            for node_id, task_result in task_results.items():
                if isinstance(task_result, dict):
                    task_text = self._extract_task_text(task_result)
                elif isinstance(task_result, str):
                    task_text = task_result
                else:
                    continue

                count, matched = self._keyword_match(keywords, task_text)
                if count > best_match_count:
                    best_match_count = count
                    best_matched = matched
                    best_node = node_id

            # Require at least 30 % keyword coverage to consider it addressed
            coverage = best_match_count / len(keywords) if keywords else 0.0
            threshold = 0.30

            if coverage >= threshold:
                status = "passed"
                evidence = (
                    f"Keyword match {best_match_count}/{len(keywords)} "
                    f"({coverage:.0%}) in task '{best_node}': "
                    f"{', '.join(best_matched[:5])}"
                )
            else:
                status = "failed"
                evidence = (
                    f"Insufficient keyword match {best_match_count}/{len(keywords)} "
                    f"({coverage:.0%}); threshold {threshold:.0%}. "
                    f"Best task '{best_node}' matched: "
                    f"{', '.join(best_matched[:5]) if best_matched else 'none'}"
                )

            requirements_met.append(RequirementCheck(
                requirement_id=req_id,
                description=description,
                status=status,
                evidence=evidence,
            ))

        # ── STATE 4: VALIDATING_ACCEPTANCE ──────────────────────────
        self._transition_state(VerificationState.VALIDATING_ACCEPTANCE)

        acceptance_met: list[RequirementCheck] = []
        all_requirements_passed = all(r.status == "passed" for r in requirements_met)

        for ac in acceptance_criteria:
            if not isinstance(ac, dict):
                continue

            ac_id = ac.get("id", "AC-???")
            description = ac.get("description", "")

            # Keyword-match the acceptance criteria description against the corpus
            keywords = self._extract_keywords(description)

            if not task_results or not corpus.strip():
                acceptance_met.append(RequirementCheck(
                    requirement_id=ac_id,
                    description=description,
                    status="failed",
                    evidence="No task results provided",
                ))
                continue

            if not keywords:
                status = "passed" if all_requirements_passed else "failed"
                evidence = (
                    "All requirements passed (generic criterion)"
                    if all_requirements_passed
                    else "Requirements not fully met (generic criterion)"
                )
            else:
                count, matched = self._keyword_match(keywords, corpus)
                coverage = count / len(keywords) if keywords else 0.0
                threshold = 0.30

                if coverage >= threshold and all_requirements_passed:
                    status = "passed"
                    evidence = (
                        f"Criteria keywords matched ({count}/{len(keywords)}, "
                        f"{coverage:.0%}) and all requirements passed: "
                        f"{', '.join(matched[:5])}"
                    )
                elif coverage >= threshold:
                    status = "failed"
                    evidence = (
                        f"Criteria keywords matched ({count}/{len(keywords)}, "
                        f"{coverage:.0%}) but not all requirements passed"
                    )
                else:
                    status = "failed"
                    evidence = (
                        f"Insufficient keyword match ({count}/{len(keywords)}, "
                        f"{coverage:.0%}): {', '.join(matched[:5]) if matched else 'none'}"
                    )

            acceptance_met.append(RequirementCheck(
                requirement_id=ac_id,
                description=description,
                status=status,
                evidence=evidence,
            ))

        all_acceptance_passed = all(r.status == "passed" for r in acceptance_met)

        # ── STATE 5: CHECKING_QUALITY ───────────────────────────────
        self._transition_state(VerificationState.CHECKING_QUALITY)

        # PHASE 7: TEST_EXIT_CODE is primary pass/fail signal
        # Pattern matching (test_coverage via _score_test_coverage) is SUPPLEMENTARY only
        code_quality = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        
        # Primary test signal: exit_code from structured TestResult
        if test_coverage_verified and test_exit_code == 0:
            # Tests ran successfully - this is PRIMARY evidence of implementation quality
            # Set high test coverage score based on verified execution
            test_coverage = min(1.0, test_coverage_verified and (1.0 if test_exit_code == 0 else 0.5))
        else:
            # Fallback to pattern-based detection as supplementary evidence only
            test_coverage = self._score_test_coverage(task_results)
        
        documentation = self._score_documentation(task_results)
        security = self._score_security(task_results)

        # PHASE 7: Weighted scoring with TEST_EXIT_CODE taking precedence
        # If tests passed (exit_code==0), verification should PASS regardless of pattern scores
        if test_coverage_verified and test_exit_code == 0:
            # Tests provide strong evidence - boost overall significantly
            test_weight = 0.40  # Increased weight for verified tests
            overall = (
                code_quality * 0.25
                + test_coverage * test_weight
                + documentation * 0.15
                + security * 0.20
            )
        else:
            # No verified tests - use traditional weighted average
            overall = (
                code_quality * 0.35
                + test_coverage * 0.25
                + documentation * 0.15
                + security * 0.25
            )

        quality_score = QualityScore(
            code_quality=round(code_quality, 4),
            test_coverage=round(test_coverage, 4),
            documentation=round(documentation, 4),
            security=round(security, 4),
            overall=round(overall, 4),
        )

        logger.info(
            "Quality — code:%.2f  test:%.2f  doc:%.2f  sec:%.2f  overall:%.2f",
            code_quality, test_coverage, documentation, security, overall,
        )

        # ── STATE 6: VERIFYING_REGRESSION ───────────────────────────
        self._transition_state(VerificationState.VERIFYING_REGRESSION)

        regression_results = self._compute_regression_results(task_results)
        if regression_results:
            logger.warning("Regression indicators found: %d", len(regression_results))

        # ── STATE 7: REVIEWING_SECURITY ─────────────────────────────
        self._transition_state(VerificationState.REVIEWING_SECURITY)

        security_findings = self._compute_security_findings(task_results)
        if security_findings:
            logger.info("Security findings: %d", len(security_findings))

        # ── STATE 8: GENERATING_REPORT ──────────────────────────────
        self._transition_state(VerificationState.GENERATING_REPORT)

        quality_ok = quality_score.overall >= verification_config.min_quality_score

        # ── PHASE 7: TEST_EXIT_CODE is PRIMARY pass/fail signal ──
        # Pattern matching (keyword coverage, etc.) is SUPPLEMENTARY only
        
        if test_coverage_verified and test_exit_code == 0:
            # Strong evidence: tests ran and passed
            # If requirements+acceptance are met AND tests pass → PASS
            if all_requirements_passed and all_acceptance_passed:
                overall_status = "passed"
            elif all_requirements_passed and all_acceptance_passed and quality_ok:
                overall_status = "passed"
            else:
                # Requirements failed but tests passed → partial at best
                overall_status = "partial"
        elif test_exit_code != -1 and test_exit_code != 0:
            # Tests ran but FAILED - this is strong negative evidence
            overall_status = "failed"
        else:
            # No test execution data - fall back to pattern-based assessment
            if all_requirements_passed and all_acceptance_passed and quality_ok:
                overall_status = "passed"
            elif all_requirements_passed and all_acceptance_passed:
                overall_status = "partial"
            else:
                overall_status = "failed"
        
        logger.info(f"Overall status: {overall_status} (tests_verified={test_coverage_verified}, exit_code={test_exit_code})")

        # Build context-aware recommendations
        recommendations: list[str] = []
        if test_coverage < 0.5:
            recommendations.append(
                f"Test coverage is low ({test_coverage:.0%}) — add unit/integration tests"
            )
        if documentation < 0.5:
            recommendations.append(
                f"Documentation coverage is low ({documentation:.0%}) — add README, docstrings, or inline comments"
            )
        if security < 0.5:
            recommendations.append(
                f"Security pattern coverage is low ({security:.0%}) — review auth, validation, and sanitization"
            )
        if code_quality < 1.0:
            failed_count = total_tasks - completed_tasks
            recommendations.append(
                f"{failed_count} of {total_tasks} task(s) did not complete successfully"
            )
        if regression_results:
            recommendations.append(
                f"{len(regression_results)} potential regression indicator(s) detected — review breaking changes"
            )

        blocking_issues: list[str] = []
        if overall_status == "failed":
            # PHASE 7: Highlight test failures first
            if not test_coverage_verified or (test_exit_code != -1 and test_exit_code != 0):
                test_summary = "Tests failed to execute" if test_exit_code == -1 else f"Tests failed with exit code {test_exit_code}"
                blocking_issues.insert(0, f"{test_summary}")
            
            failed_reqs = [r for r in requirements_met if r.status != "passed"]
            if failed_reqs:
                blocking_issues.append(
                    f"{len(failed_reqs)} requirement(s) not met: "
                    + ", ".join(r.requirement_id for r in failed_reqs[:5])
                )
            failed_acs = [r for r in acceptance_met if r.status != "passed"]
            if failed_acs:
                blocking_issues.append(
                    f"{len(failed_acs)} acceptance criteria not met: "
                    + ", ".join(r.requirement_id for r in failed_acs[:5])
                )
            if not quality_ok:
                blocking_issues.append(
                    f"Quality score ({quality_score.overall:.0%}) below minimum "
                    f"({verification_config.min_quality_score:.0%})"
                )

        report = VerificationReport(
            brief_id=brief_id,
            requirements_met=requirements_met,
            acceptance_met=acceptance_met,
            quality_score=quality_score,
            regression_results=regression_results,
            security_findings=security_findings,
            recommendations=recommendations,
            blocking_issues=blocking_issues,
            overall_status=overall_status,
            test_results=test_results_processed,  # PHASE 7: Include structured test results
            test_exit_code=test_exit_code,  # PHASE 7: Primary pass/fail signal
            test_coverage_verified=test_coverage_verified,  # PHASE 7: Whether tests actually ran
        )

        # Persist to database
        from storage.models import VerificationSession
        session_model = VerificationSession(
            id=report.verification_id,
            brief_id=brief_id,
            requirements_met=[
                {"requirement_id": r.requirement_id, "status": r.status, "evidence": r.evidence}
                for r in requirements_met
            ],
            acceptance_met=[
                {"requirement_id": r.requirement_id, "status": r.status, "evidence": r.evidence}
                for r in acceptance_met
            ],
            quality_score={
                "code_quality": quality_score.code_quality,
                "test_coverage": quality_score.test_coverage,
                "documentation": quality_score.documentation,
                "security": quality_score.security,
                "overall": quality_score.overall,
            },
            overall_status=overall_status,
            recommendations=report.recommendations,
            blocking_issues=report.blocking_issues,
        )
        self.session.add(session_model)
        await self.session.flush()

        # ── Terminal state ──────────────────────────────────────────
        if overall_status == "passed":
            self._transition_state(VerificationState.VERIFICATION_COMPLETE)
        else:
            self._transition_state(VerificationState.VERIFICATION_FAILED)

        return VerificationResult(
            state=self._current_state,
            report=report,
            message=self._build_verification_message(report),
            metadata={
                "verification_id": report.verification_id,
                "brief_id": brief_id,
                "overall_status": overall_status,
                "quality_score": quality_score.overall,
                "quality_breakdown": {
                    "code_quality": quality_score.code_quality,
                    "test_coverage": quality_score.test_coverage,
                    "documentation": quality_score.documentation,
                    "security": quality_score.security,
                },
                "regression_indicators": len(regression_results),
                "security_findings": len(security_findings),
            },
        )

    def _build_verification_message(self, report: VerificationReport) -> str:
        """Build user-facing verification message."""
        lines = [
            "**Verification Complete**\n",
            f"- Status: {report.overall_status.upper()}",
            f"- Requirements: {len(report.requirements_met)} checked",
            f"- Acceptance: {len(report.acceptance_met)} checked",
            f"- Quality Score: {report.quality_score.overall:.0%}",
        ]

        if report.blocking_issues:
            lines.append("\nBlocking issues:")
            for issue in report.blocking_issues:
                lines.append(f"  - {issue}")

        if report.recommendations:
            lines.append("\nRecommendations:")
            for rec in report.recommendations[:3]:
                lines.append(f"  - {rec}")

        if report.overall_status == "passed":
            lines.append("\nReply **yes / go ahead** to deliver.")

        return "\n".join(lines)
