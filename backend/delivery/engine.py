"""Delivery & Continuous Improvement — Core Engine.

Delivers verified engineering output and learns from outcomes.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from delivery.config import delivery_config
from delivery.models import EngineeringReport, LessonLearned, DeliveryResult

logger = logging.getLogger("aic.delivery")


class DeliveryEngine:
    """Delivery & Continuous Improvement Engine."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self._reports: list[EngineeringReport] = []
        self._lessons: list[LessonLearned] = []

    async def generate_report(
        self,
        brief_id: str,
        plan_id: str = "",
        graph_id: str = "",
        verification_id: str = "",
        task_results: dict | None = None,
    ) -> EngineeringReport:
        """Generate an engineering report.

        Args:
            brief_id: Brief ID
            plan_id: Plan ID
            graph_id: Graph ID
            verification_id: Verification ID
            task_results: Task execution results

        Returns:
            EngineeringReport
        """
        if not delivery_config.enabled:
            return EngineeringReport(brief_id=brief_id)

        # Calculate metrics
        total_tasks = len(task_results) if task_results else 0
        successful = sum(
            1 for r in (task_results or {}).values()
            if isinstance(r, dict) and r.get("status") == "completed"
        )

        # Determine outcome
        if total_tasks == 0:
            outcome = "pending"
        elif successful == total_tasks:
            outcome = "success"
        elif successful > 0:
            outcome = "partial"
        else:
            outcome = "failure"

        # Extract lessons
        lessons = []
        if delivery_config.extract_lessons:
            lessons = await self._extract_lessons(task_results)

        # Generate recommendations
        recommendations = self._generate_recommendations(outcome, total_tasks, successful)

        report = EngineeringReport(
            brief_id=brief_id,
            plan_id=plan_id,
            graph_id=graph_id,
            verification_id=verification_id,
            goal=f"Engineering delivery for {brief_id}",
            outcome=outcome,
            total_tasks=total_tasks,
            successful_tasks=successful,
            failed_tasks=total_tasks - successful,
            lessons=lessons,
            recommendations=recommendations,
            status="final",
        )

        # Persist to database if session available
        if self.session:
            from storage.models import EngineeringReport as EngineeringReportORM
            report_model = EngineeringReportORM(
                id=report.report_id,
                brief_id=brief_id,
                plan_id=plan_id,
                graph_id=graph_id,
                verification_id=verification_id,
                goal=report.goal,
                outcome=outcome,
                total_tasks=total_tasks,
                successful_tasks=successful,
                failed_tasks=total_tasks - successful,
                lessons=[{"lesson": l.lesson, "category": l.category} for l in lessons],
                recommendations=recommendations,
                status="final",
            )
            self.session.add(report_model)
            await self.session.flush()

            # Persist lessons
            from storage.models import LessonLearned as LessonLearnedORM
            for lesson in lessons:
                lesson_model = LessonLearnedORM(
                    id=lesson.id,
                    report_id=report.report_id,
                    lesson=lesson.lesson,
                    category=lesson.category,
                    impact=lesson.impact,
                    recommendation=lesson.recommendation,
                )
                self.session.add(lesson_model)
            await self.session.flush()
        else:
            self._reports.append(report)
            self._lessons.extend(lessons)

        return report

    async def deliver(
        self,
        brief_id: str,
        **kwargs,
    ) -> DeliveryResult:
        """Complete delivery pipeline.

        Args:
            brief_id: Brief ID
            **kwargs: Additional arguments

        Returns:
            DeliveryResult
        """
        # Generate report
        report = await self.generate_report(brief_id, **kwargs)

        return DeliveryResult(
            report=report,
            message=self._build_delivery_message(report),
            metadata={
                "report_id": report.report_id,
                "outcome": report.outcome,
                "lessons_count": len(report.lessons),
            },
        )

    async def _extract_lessons(
        self,
        task_results: dict | None,
    ) -> list[LessonLearned]:
        """Extract lessons from execution results."""
        lessons = []

        # Extract from failed tasks
        for node_id, result in (task_results or {}).items():
            if isinstance(result, dict) and result.get("status") == "failed":
                lessons.append(LessonLearned(
                    lesson=f"Task {node_id} failed",
                    category="execution",
                    impact="medium",
                    recommendation="Investigate failure cause",
                ))

        return lessons

    def _generate_recommendations(
        self,
        outcome: str,
        total_tasks: int,
        successful: int,
    ) -> list[str]:
        """Generate recommendations based on outcome."""
        recommendations = []

        if outcome == "failure":
            recommendations.append("Review failure causes and adjust approach")
        elif outcome == "partial":
            recommendations.append("Investigate failed tasks for patterns")
        else:
            recommendations.append("Document successful approach for future reference")

        if total_tasks > 10:
            recommendations.append("Consider breaking large tasks into smaller chunks")

        return recommendations

    def _build_delivery_message(self, report: EngineeringReport) -> str:
        """Build user-facing delivery message."""
        lines = [
            "**Engineering Delivery Complete**\n",
            f"- Outcome: {report.outcome.upper()}",
            f"- Tasks: {report.successful_tasks}/{report.total_tasks} successful",
            f"- Quality: {report.quality_score:.0%}",
        ]

        if report.lessons:
            lines.append(f"\nLessons learned: {len(report.lessons)}")

        if report.recommendations:
            lines.append("\nRecommendations:")
            for rec in report.recommendations[:3]:
                lines.append(f"  - {rec}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get delivery statistics."""
        outcomes = {}
        for report in self._reports:
            outcomes[report.outcome] = outcomes.get(report.outcome, 0) + 1

        return {
            "total_reports": len(self._reports),
            "total_lessons": len(self._lessons),
            "outcomes": outcomes,
        }


# Singleton
delivery_engine = DeliveryEngine()
