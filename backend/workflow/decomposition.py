"""Task decomposition: breaks complex tasks into subtasks with dependencies.

Called during the planning phase after the architect produces a decomposition plan.
Subtasks are created as child Task rows with parent_task_id, subtask_order, and depends_on.
"""
import json
import re
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from storage.models import Task, TaskStatus, TaskType

logger = logging.getLogger(__name__)

# Keywords used to infer a worker type from structured plan requirement text
# (mirrors taskgraph.decomposer.WORKER_TYPE_MAP heuristics).
_WORKER_KEYWORDS = {
    "database": "database",
    "schema": "database",
    "migration": "database",
    "api": "backend",
    "endpoint": "backend",
    "backend": "backend",
    "server": "backend",
    "auth": "backend",
    "frontend": "frontend",
    "ui": "frontend",
    "component": "frontend",
    "page": "frontend",
    "test": "qa",
    "coverage": "qa",
    "security": "security",
    "audit": "security",
    "doc": "documentation",
    "readme": "documentation",
    "deploy": "devops",
    "devops": "devops",
    "ci": "devops",
}

# Parent context keys inherited by subtasks so they run in the same
# conversation/workspace scope as the parent task.
_INHERITED_CONTEXT_KEYS = (
    "conversation_id",
    "workspace",
    "repo_path",
    "project_slug",
    "model_tier",
)


def _infer_worker_type(text: str) -> str:
    """Infer a worker type from requirement text via keyword heuristics."""
    lower = (text or "").lower()
    for keyword, worker in _WORKER_KEYWORDS.items():
        if keyword in lower:
            return worker
    return "backend"


def specs_from_plan_data(plan_data: dict) -> list[dict]:
    """Build subtask specs from a structured EngineeringPlan.

    The production planning stage persists a structured plan (engineering_goal,
    effort_estimates=[{requirement_id, complexity, ...}], optional
    functional_requirements=[{id, description, ...}]) rather than free-form
    architect markdown. This converts that real shape into subtask specs.

    Returns [] when the plan yields fewer than 2 subtasks (nothing to
    decompose).
    """
    if not isinstance(plan_data, dict):
        return []

    estimates = plan_data.get("effort_estimates") or []
    requirements = plan_data.get("functional_requirements") or []
    goal = str(plan_data.get("engineering_goal") or "").strip()

    # Index functional requirements by id for description enrichment
    req_by_id = {}
    for req in requirements:
        if isinstance(req, dict) and req.get("id"):
            req_by_id[str(req["id"])] = req

    specs = []
    for i, est in enumerate(estimates):
        if not isinstance(est, dict):
            continue
        req_id = str(est.get("requirement_id") or f"REQ-{i + 1}")
        req = req_by_id.get(req_id, {})
        description = str(req.get("description") or est.get("description") or "").strip()
        title = f"{req_id}: {description[:120]}" if description else f"{req_id}: {goal[:100] or 'Implementation step'}"
        complexity = str(est.get("complexity") or "medium")
        specs.append({
            "title": title.strip(),
            "worker_type": _infer_worker_type(description or title),
            "depends_on": [],
            "description": f"{description} (complexity: {complexity})"[:500] if description else f"Goal: {goal}"[:500],
            "order": len(specs) + 1,
        })

    # A single requirement is not a decomposition — fall back to goal-based
    # split only when there is a goal and no estimates at all.
    if len(specs) <= 1:
        return []

    return specs



def parse_decomposition(architect_output: str) -> list[dict]:
    """Parse architect LLM output into a list of subtask specs.

    Handles multiple formats:
    - Markdown sections: ## Subtask 1: Title / ### 1. Title / ## 1. Title
    - JSON arrays
    - Numbered lists with worker assignments
    - Bullet lists with worker: tags
    """
    subtasks = []

    # Try JSON format first
    try:
        data = json.loads(architect_output)
        if isinstance(data, list):
            for i, item in enumerate(data):
                subtasks.append({
                    "title": str(item.get("title", f"Subtask {i+1}")),
                    "worker_type": str(item.get("worker_type", item.get("worker", "backend"))).lower(),
                    "depends_on": item.get("depends_on", []),
                    "description": str(item.get("description", "")),
                    "order": i + 1,
                })
            return subtasks
    except (json.JSONDecodeError, TypeError):
        pass

    # Try markdown sections — multiple heading patterns
    # Matches: ## Subtask 1: Title, ## Task 1: Title, ### 1. Title, ## 1. Title, ## Step 1: Title
    pattern = r'^#{1,4}\s*(?:Subtask|Task|Step|Phase)?\s*\d+[:.)]?\s*(.+?)(?=\n#{1,4}\s*(?:Subtask|Task|Step|Phase)?\s*\d+|$)'
    sections = re.findall(pattern, architect_output, re.DOTALL | re.MULTILINE)

    # Also try: numbered list items with bold titles
    if not sections:
        pattern2 = r'^\d+[.)]\s+\*\*(.+?)\*\*[:\s]*(.+?)(?=\n\d+[.)]|\n##|\Z)'
        sections = re.findall(pattern2, architect_output, re.DOTALL | re.MULTILINE)
        sections = [f"{s[0]}\n{s[1]}" for s in sections]

    # Also try: numbered list items
    if not sections:
        pattern3 = r'^\d+[.)]\s+(.+?)(?=\n\d+[.)]|\n##|\Z)'
        sections = re.findall(pattern3, architect_output, re.DOTALL | re.MULTILINE)

    # Also try: bullet items with worker tags
    if not sections:
        pattern4 = r'^[-*]\s+(.+?)(?=\n[-*]\s+|\n##|\Z)'
        sections = re.findall(pattern4, architect_output, re.DOTALL | re.MULTILINE)
        # Only use if any section mentions a worker
        if sections and not any("worker" in s.lower() or "backend" in s.lower() or "frontend" in s.lower() for s in sections):
            sections = []

    if not sections:
        return []

    for i, section in enumerate(sections):
        lines = section.strip().split("\n")
        title = lines[0].strip() if lines else f"Subtask {i+1}"
        # Clean title: remove ** markers, trailing colons
        title = re.sub(r'\*\*', '', title).strip().rstrip(':')
        worker = "backend"
        depends = []
        desc_lines = []
        full_text = section.lower()

        # Extract worker from inline patterns: (worker: backend), worker: backend, (backend)
        worker_match = re.search(r'worker[:\s]+(\w+)', full_text)
        if not worker_match:
            # Try parenthetical: (backend), (frontend), etc
            for w in ["backend", "frontend", "database", "qa", "security", "designer", "architect", "documentation", "devops", "performance"]:
                if w in full_text:
                    worker = w
                    break
        else:
            worker = worker_match.group(1).lower()

        # Also check explicit - Worker: lines
        for line in lines:
            ll = line.lower().strip()
            if ll.startswith("- worker:") or ll.startswith("* worker:") or ll.startswith("worker:"):
                worker = line.split(":", 1)[1].strip().lower()
            elif "depends on" in ll:
                dep_str = ll.split(":", 1)[-1].strip() if ":" in ll else ""
                if dep_str and dep_str != "none":
                    depends = [d.strip() for d in dep_str.split(",")]
            elif line.strip() and not line.strip().startswith("-") and not line.strip().startswith("*"):
                desc_lines.append(line.strip())

        subtasks.append({
            "title": title,
            "worker_type": worker,
            "depends_on": depends,
            "description": " ".join(desc_lines)[:500],
            "order": i + 1,
        })

    return subtasks


async def decompose_task(session: AsyncSession, parent_task: Task, architect_output: str, plan_data: dict | None = None) -> list[Task]:
    """Decompose a parent task into subtasks based on architect output.

    Args:
        session: Async database session
        parent_task: Parent Task to decompose
        architect_output: Free-form architect output (Markdown sections, JSON, numbered lists)
        plan_data: Optional structured EngineeringPlan dict fallback with effort_estimates
                   and functional_requirements. Used when architect_output doesn't parse
                   into multiple subtasks. This handles the real production shape where the
                   planning stage persists a structured plan rather than free-form markdown.

    Returns:
        List of created subtask Tasks (empty if no decomposition or only one spec).

    Context Inheritance:
        Subtasks inherit conversation/workspace/repo_path keys from the parent's context so
        they execute in the same sandbox scope as the parent task (see executor sandbox
        resolution which keys off context["conversation_id"]).
    """
    specs = parse_decomposition(architect_output)

    # Fallback to structured plan parsing when architect output is unparseable
    # or yields too few specs. This handles the actual production shape where the
    # planning stage persists a structured EngineeringPlan rather than free-form markdown.
    if len(specs) <= 1 and plan_data:
        logger.info(f"Task {parent_task.id[:8]}: falling back to structured plan parsing")
        plan_specs = specs_from_plan_data(plan_data)
        if plan_specs and len(plan_specs) > 1:
            specs = plan_specs

    if not specs:
        logger.info(f"Task {parent_task.id[:8]}: no decomposition parseable, treating as single task")
        return []

    if len(specs) <= 1:
        logger.info(f"Task {parent_task.id[:8]}: only {len(specs)} subtask, no decomposition needed")
        return []

    logger.info(f"Task {parent_task.id[:8]}: decomposing into {len(specs)} subtasks")
    created = []

    # Map subtask titles to IDs for dependency resolution (lowercase key)
    title_to_id = {}

    # Inherit conversation/workspace/repo_path context from parent so subtasks
    # execute in the same sandbox scope as the parent task.
    parent_ctx = parent_task.context or {}
    inherited = {k: v for k, v in parent_ctx.items() if k in _INHERITED_CONTEXT_KEYS}

    for spec in specs:
        subtask = Task(
            project_id=parent_task.project_id,
            title=spec["title"],
            description=spec["description"] or parent_task.description,
            type=parent_task.type,
            status=TaskStatus.CREATED.value,
            worker_type=spec["worker_type"],
            approval_required=parent_task.approval_required,
            progress=0,
            context={**inherited, "parent_task_id": parent_task.id, "decomposed": True},
            parent_task_id=parent_task.id,
            subtask_order=spec["order"],
            depends_on=[],
            created_by=parent_task.created_by,
        )
        session.add(subtask)
        await session.flush()  # get ID
        title_to_id[spec["title"].lower()] = subtask.id
        created.append(subtask)
        logger.info(f"  Subtask {subtask.id[:8]}: {spec['title']} → {spec['worker_type']}")

    # Resolve dependencies: map dependency names to subtask IDs
    for i, spec in enumerate(specs):
        if spec["depends_on"]:
            dep_ids = []
            for dep_name in spec["depends_on"]:
                dep_id = title_to_id.get(dep_name.lower())
                if dep_id:
                    dep_ids.append(dep_id)
                else:
                    # Try matching by order number
                    try:
                        order = int(dep_name)
                        if 1 <= order <= len(created):
                            dep_ids.append(created[order - 1].id)
                    except ValueError:
                        pass
            created[i].depends_on = dep_ids
            logger.info(f"  Subtask {created[i].id[:8]} depends on: {[d[:8] for d in dep_ids]}")

    # Mark parent as decomposed — it will coordinate subtasks
    parent_task.context = parent_task.context or {}
    parent_task.context["decomposed"] = True
    parent_task.context["subtask_ids"] = [t.id for t in created]
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(parent_task, "context")

    await session.commit()

    # Emit event
    from storage.models import Event, EventType
    session.add(Event(
        type=EventType.TASK_CREATED.value,
        actor="system:architect",
        target=f"task:{parent_task.id}",
        data={"action": "decomposed", "subtask_count": len(created), "subtask_ids": [t.id for t in created]},
        severity="info"
    ))
    await session.commit()

    return created


async def get_ready_subtasks(session: AsyncSession, parent_task_id: str) -> list[Task]:
    """Get subtasks whose dependencies are all completed."""
    result = await session.execute(
        select(Task).where(Task.parent_task_id == parent_task_id).order_by(Task.subtask_order)
    )
    subtasks = result.scalars().all()

    ready = []
    for st in subtasks:
        if st.status != TaskStatus.CREATED.value:
            continue
        if not st.depends_on:
            ready.append(st)
            continue
        # Check all dependencies are completed
        deps_completed = True
        for dep_id in st.depends_on:
            dep_result = await session.execute(select(Task).where(Task.id == dep_id))
            dep = dep_result.scalar_one_or_none()
            if not dep or dep.status != TaskStatus.COMPLETED.value:
                deps_completed = False
                break
        if deps_completed:
            ready.append(st)

    return ready


async def get_subtasks(session: AsyncSession, parent_task_id: str) -> list[Task]:
    """Get all subtasks for a parent task."""
    result = await session.execute(
        select(Task).where(Task.parent_task_id == parent_task_id).order_by(Task.subtask_order)
    )
    return list(result.scalars().all())
