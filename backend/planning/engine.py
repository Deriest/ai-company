"""Planning Engine — Core Orchestrator.

Main entry point for the Planning Engine.
Transforms Engineering Briefs into structured Engineering Plans.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import EngineeringBrief as EngineeringBriefModel, EngineeringPlan as EngineeringPlanModel
from planning.config import planning_config
from planning.states import PlanningState
from planning.models import (
    EngineeringPlan,
    ArchitectureDecision, RiskMitigation, DependencyMap,
    EffortEstimate, AcceptanceCriterion,
)
from planning.analyzer import BriefAnalyzer, BriefAnalysis
from planning.decision import DecisionMaker
from planning.risk import RiskAssessor
from planning.effort import EffortEstimator
from planning.validator import PlanValidator

logger = logging.getLogger("aic.planning")


class PlanningResult:
    """Result of a planning operation."""

    def __init__(
        self,
        state: str,
        plan: EngineeringPlan | None = None,
        message: str = "",
        metadata: dict | None = None,
    ):
        self.state = state
        self.plan = plan
        self.message = message
        self.metadata = metadata or {}


class PlanningEngine:
    """Planning Engine — transforms Briefs into Plans."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def plan(
        self,
        brief_id: str,
        project_context: dict | None = None,
    ) -> PlanningResult:
        """Generate an Engineering Plan from a Brief.

        Args:
            brief_id: Engineering Brief ID
            project_context: Optional project context

        Returns:
            PlanningResult with plan or error
        """
        if not planning_config.enabled:
            return PlanningResult(
                state="disabled",
                message="Planning is disabled",
            )

        # Load brief
        result = await self.session.execute(
            select(EngineeringBriefModel).where(EngineeringBriefModel.id == brief_id)
        )
        brief_model = result.scalar_one_or_none()

        if not brief_model:
            return PlanningResult(
                state="error",
                message=f"Brief not found: {brief_id}",
            )

        # Convert brief to dict
        brief_data = {
            "id": brief_model.id,
            "engineering_goal": brief_model.engineering_goal,
            "user_intent": brief_model.user_intent,
            "request_category": brief_model.request_category,
            "scope": brief_model.scope or {},
            "functional_requirements": brief_model.functional_requirements or [],
            "non_functional_requirements": brief_model.non_functional_requirements or [],
            "constraints": brief_model.constraints or [],
            "assumptions": brief_model.assumptions or [],
            "dependencies": brief_model.dependencies or [],
            "risks": brief_model.risks or [],
            "acceptance_criteria": brief_model.acceptance_criteria or [],
            "readiness_score": brief_model.readiness_score,
            "outstanding_unknowns": brief_model.outstanding_unknowns or [],
        }

        # Run planning pipeline
        return await self._run_pipeline(brief_data, project_context)

    async def _run_pipeline(
        self,
        brief_data: dict,
        project_context: dict | None = None,
    ) -> PlanningResult:
        """Run the planning pipeline.

        Pipeline: Analyze → Decide → Estimate → Generate → Validate
        """
        # Step 1: Analyze brief
        analysis = BriefAnalyzer.analyze(brief_data)

        # Step 2: Make decisions
        decisions = DecisionMaker.make_decisions(analysis, brief_data)
        strategy = DecisionMaker.select_strategy(analysis)

        # Step 3: Assess risks
        risks = RiskAssessor.assess_risks(analysis, brief_data)

        # Step 4: Estimate effort
        effort_estimates = EffortEstimator.estimate_effort(analysis, brief_data)
        duration = EffortEstimator.estimate_total_duration(effort_estimates)

        # Step 5: Generate plan
        plan = self._generate_plan(
            brief_data, analysis, decisions, strategy,
            risks, effort_estimates, duration
        )

        # Step 6: Calculate confidence
        plan.confidence_score = PlanValidator.calculate_confidence(plan)

        # Step 7: Validate
        validation = PlanValidator.validate(plan)

        if validation.is_valid:
            plan.status = "validated"

            # Persist to database
            plan_model = EngineeringPlanModel(
                id=plan.id,
                brief_id=plan.brief_id,
                engineering_goal=plan.engineering_goal,
                technical_approach=plan.technical_approach,
                implementation_strategy=plan.implementation_strategy,
                architecture_decisions=[
                    {"decision": d.decision, "rationale": d.rationale, "risk_level": d.risk_level}
                    for d in plan.architecture_decisions
                ],
                risk_mitigations=[
                    {"risk": r.risk, "likelihood": r.likelihood, "impact": r.impact, "mitigation": r.mitigation}
                    for r in plan.risk_mitigations
                ],
                dependency_map={
                    "external": plan.dependency_map.external,
                    "internal": plan.dependency_map.internal,
                },
                effort_estimates=[
                    {"requirement_id": e.requirement_id, "complexity": e.complexity, "estimated_hours": e.estimated_hours}
                    for e in plan.effort_estimates
                ],
                acceptance_criteria=[
                    {"id": a.id, "description": a.description}
                    for a in plan.acceptance_criteria
                ],
                estimated_duration=plan.estimated_duration,
                confidence_score=plan.confidence_score,
                status=plan.status,
            )
            self.session.add(plan_model)
            await self.session.flush()

            return PlanningResult(
                state=PlanningState.PLAN_COMPLETE.value,
                plan=plan,
                message=self._build_plan_message(plan, analysis),
                metadata={
                    "plan_id": plan.id,
                    "brief_id": brief_data.get("id"),
                    "strategy": strategy,
                    "complexity": analysis.complexity,
                    "confidence": plan.confidence_score,
                },
            )
        else:
            return PlanningResult(
                state=PlanningState.ERROR.value,
                message=f"Plan validation failed: {'; '.join(validation.errors)}",
                metadata={"errors": validation.errors, "warnings": validation.warnings},
            )

    def _generate_plan(
        self,
        brief_data: dict,
        analysis: BriefAnalysis,
        decisions: list[ArchitectureDecision],
        strategy: str,
        risks: list[RiskMitigation],
        effort_estimates: list[EffortEstimate],
        duration: str,
    ) -> EngineeringPlan:
        """Generate an Engineering Plan from analysis results."""
        # Build technical approach
        technical_approach = self._build_technical_approach(analysis, decisions)

        # Build acceptance criteria from brief
        acceptance_criteria = []
        for i, ac in enumerate(brief_data.get("acceptance_criteria", []), 1):
            if isinstance(ac, dict):
                acceptance_criteria.append(AcceptanceCriterion(
                    id=ac.get("id", f"AC-{i:03d}"),
                    description=ac.get("description", ""),
                    verification_method=ac.get("verification_method", "manual"),
                ))

        # Build dependency map
        dependencies = brief_data.get("dependencies", [])
        dependency_map = DependencyMap(
            external=[d.get("description", str(d)) for d in dependencies if isinstance(d, dict)],
            internal=analysis.affected_components,
            circular=[],
        )

        return EngineeringPlan(
            brief_id=brief_data.get("id", ""),
            engineering_goal=brief_data.get("engineering_goal", ""),
            technical_approach=technical_approach,
            implementation_strategy=strategy,
            architecture_decisions=decisions,
            risk_mitigations=risks,
            dependency_map=dependency_map,
            effort_estimates=effort_estimates,
            acceptance_criteria=acceptance_criteria,
            estimated_duration=duration,
            confidence_score=0.0,  # Will be calculated
            status="draft",
        )

    def _build_technical_approach(
        self,
        analysis: BriefAnalysis,
        decisions: list[ArchitectureDecision],
    ) -> str:
        """Build technical approach description."""
        parts = []

        # Overall approach
        parts.append(f"Implement {analysis.complexity} complexity changes")

        # Components
        if analysis.affected_components:
            parts.append(f"affecting {', '.join(analysis.affected_components)}")

        # Strategy
        parts.append("using component-based architecture")

        # Key decisions
        if decisions:
            key_decisions = [d.decision for d in decisions[:3]]
            parts.append(f"with {', '.join(key_decisions)}")

        return ". ".join(parts) + "."

    def _build_plan_message(
        self,
        plan: EngineeringPlan,
        analysis: BriefAnalysis,
    ) -> str:
        """Build user-facing plan message."""
        lines = [
            "**Engineering Plan Generated**\n",
            f"- Goal: {plan.engineering_goal[:100]}",
            f"- Strategy: {plan.implementation_strategy.title()}",
            f"- Complexity: {analysis.complexity.title()}",
            f"- Duration: {plan.estimated_duration}",
            f"- Confidence: {plan.confidence_score:.0%}",
        ]

        if plan.architecture_decisions:
            lines.append(f"- Decisions: {len(plan.architecture_decisions)}")

        if plan.risk_mitigations:
            lines.append(f"- Risks identified: {len(plan.risk_mitigations)}")

        lines.append("\nReply **yes / go ahead** to generate Task Graph.")

        return "\n".join(lines)
