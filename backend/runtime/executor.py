"""AIC Platform — Unified Runtime Executor.

Single execution engine with Smart Triage, Adaptive Execution & Local Repair.

Executes tasks through FSM phases adaptively based on Smart Triage execution levels:
- L1 QUICK: Fast-path for localized changes, skipping unnecessary phases (discovery/planning/closeout).
- L2 STANDARD: Normal scoped engineering.
- L3 EXTENDED: Cross-component / higher-risk engineering.
- L4 FULL: Complete multi-agent lifecycle.

Integrity rules:
- Task is NOT marked COMPLETED if verification phase has any failed worker.
- Fallback/template output NEVER masquerades as successful engineering.
- Verification failure triggers localized repair loop before full escalation.
- Smart Triage guardrails enforce minimum safety levels (security, DB schema, architecture).
- Events form causal chain via parent_event_id and metadata.
"""
from datetime import datetime, timezone
import asyncio
import os
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from storage.models import (
    Task, Lease, Worker, Event, EventType, TaskStatus, LeaseStatus, Approval, ApprovalStatus
)
from workers.base import WORKER_REGISTRY
from workflow.triage import perform_smart_triage, ExecutionLevel

logger = logging.getLogger("aic.runtime")


def _utcnow():
    return datetime.now(timezone.utc)


# SQLite in WAL mode permits only ONE writer at a time. When parallel phase
# workers (each with its OWN session, run via asyncio.gather) commit their
# worker.started/completed/failed events nearly simultaneously, a writer can
# block past busy_timeout and raise "database is locked". This is a real,
# transient concurrency condition — the correct fix is to retry the commit with
# a short backoff, NOT to serialize the workers or swallow other errors.
#
# The retry logic lives in the shared storage.lock_retry module so other
# subsystems (llm/provider, observability/audit) reuse the same backoff policy.
async def _commit_with_lock_retry(
    session: AsyncSession, reapply=None, attempts: int = 12
) -> None:
    """Commit *session*, retrying on the transient SQLite "database is locked"
    OperationalError. Only the locked condition is retried and re-raised by
    type; any other error propagates immediately. Backoff is 0.05s * attempt.

    When a locked failure occurs during flush, SQLAlchemy rolls back the
    transaction and expunges the pending objects (e.g. Lease/Event), so a bare
    retry would commit an empty transaction and silently drop the writes.
    ``reapply`` — an optional async callable — is invoked after rollback to
    re-establish the pending objects before the next attempt.
    """
    from storage.lock_retry import commit_with_lock_retry

    return await commit_with_lock_retry(
        session, reapply=reapply, attempts=attempts, base_delay=0.05
    )


async def _emit_event(session: AsyncSession, task_id: str, event_type: str, actor: str, target: str, data: dict, severity: str = "info"):
    """Emit an Event to the database AND broadcast via WebSocket for live observability."""
    event = Event(
        type=event_type,
        actor=actor,
        target=target,
        data=data,
        severity=severity,
    )
    session.add(event)
    try:
        from backend.routes.websocket import broadcast_task_event
        await broadcast_task_event(event_type, task_id, data)
    except Exception as e:
        logger.debug(f"WebSocket broadcast skipped: {e}")
    
    # Fire automation hooks for this event type
    try:
        from backend.services.automation_service import automation_service
        context = {
            "task_id": task_id,
            "event_type": event_type,
            "actor": actor,
            "target": target,
            "severity": severity,
            **data
        }
        await automation_service.fire_event(session, event_type, context)
    except Exception as e:
        logger.debug(f"Automation hook fire failed for {event_type}: {e}")

    # Return the created Event so callers can re-add it after a lock-retry
    # rollback (the pending object would otherwise be silently dropped).
    return event



def _adaptive_worker_timeout(worker_type: str, base_timeout: int = 120) -> int:
    """Adaptive timeout for tool-calling workers based on tier.
    
    Tool-calling workers run multi-round loops (each round = queue wait + LLM call + tool exec).
    A flat per-call budget is exhausted under parallel queueing, so scale by tier.
    """
    try:
        from agents.context_assembly import get_model_config
        _wcfg = get_model_config(worker_type)
        _base = int(_wcfg.get("timeout") or base_timeout)
        _tier = str(_wcfg.get("tier") or "crafter").lower()
        _mult = {"thinker": 2.5, "crafter": 2.5, "sprinter": 1.5}.get(_tier, 2.0)
        return max(_base, int(_base * _mult))
    except Exception:
        return base_timeout


async def execute_task(session: AsyncSession, task: Task) -> dict:
    """Execute a task through FSM phases adaptively according to Smart Triage execution level."""
    from workflow.fsm import (
        is_terminal, allowed_workers_for_phase, next_phase
    )

    # 1. Resolve Project & Repository Path
    from storage.models import Project
    from backend.workspace_manager import inspect_project_structure, save_deliverable_file
    from backend.code_extract import extract_code_blocks_to_workspace

    proj_res = await session.execute(select(Project).where(Project.id == task.project_id))
    project_obj = proj_res.scalar_one_or_none()
    # Workspace resolution: prefer the project repo_path, else fall back to a
    # per-conversation/per-task sandbox under DATA_DIR/workspaces — NEVER the
    # process cwd ("."). This keeps generated files out of an arbitrary working
    # directory when no project is linked.
    from shared.workspace import sandbox_workspace_dir
    raw_repo_path = str(project_obj.repo_path) if project_obj and project_obj.repo_path else ""
    if raw_repo_path:
        effective_repo_path = raw_repo_path
    else:
        scope_id = (task.context or {}).get("conversation_id") or task.id
        effective_repo_path = sandbox_workspace_dir(scope_id)
    project_structure = await asyncio.to_thread(inspect_project_structure, effective_repo_path)

    # 2. Resolve Smart Triage & Execution Level
    ctx = task.context or {}
    triage_data = ctx.get("triage")
    if not triage_data:
        triage_res = perform_smart_triage(
            f"{task.title} {task.description or ''}",
            task_type=task.type,
            worker_hint=task.worker_type,
        )
        triage_data = triage_res.to_dict()
        ctx["triage"] = triage_data
        ctx["execution_level"] = triage_res.level.value
        task.context = ctx
        flag_modified(task, 'context')

    execution_level = ctx.get("execution_level", ExecutionLevel.STANDARD.value)
    skip_phases = triage_data.get("skip_phases", {})
    selected_workers_list = triage_data.get("selected_workers", [])
    phase_semantics = ctx.get("phase_semantics", {})
    handoffs_dict = ctx.get("handoffs", {})

    # Materialize PRD.md from Engineering Brief if available (best-effort)
    try:
        brief_id = ctx.get("brief_id", "")
        if brief_id:
            from storage.models import EngineeringBrief
            brief_res = await session.execute(
                select(EngineeringBrief).where(EngineeringBrief.id == brief_id)
            )
            brief_obj = brief_res.scalar_one_or_none()
            if brief_obj:
                from backend.services.prd_writer import materialize_prd
                prd_path = await asyncio.to_thread(materialize_prd, effective_repo_path, brief_obj)
                if prd_path:
                    logger.info(f"Task {task.id[:8]}: PRD.md materialized -> {prd_path}")
    except Exception as e:
        logger.warning(f"Task {task.id[:8]}: Failed to materialize PRD.md (non-fatal): {e}")

    # Start from first execution phase
    phase = "discovery"
    task.status = phase
    task.progress = 5
    task.started_at = _utcnow()
    await session.flush()

    # Causal chain root event
    root_event_data = {
        "title": task.title,
        "type": task.type,
        "worker_type": task.worker_type,
        "execution_level": execution_level,
        "triage_reason": triage_data.get("reason"),
        "guardrails_triggered": triage_data.get("guardrails_triggered", []),
    }
    await _emit_event(
        session, task.id, EventType.TASK_CREATED.value, "system:dispatcher", f"task:{task.id}", root_event_data, "info"
    )
    await session.flush()

    results = {}
    phases_done = 0
    verification_failed = False
    fallback_used = False
    prev_event_target = f"task:{task.id}"

    while not is_terminal(phase):
        # 2. Check Adaptive Phase Skipping
        if phase in skip_phases:
            skip_reason = skip_phases[phase]
            logger.info(f"Task {task.id[:8]} phase={phase} SKIPPED (level={execution_level}): {skip_reason}")
            phase_semantics[phase] = "SKIPPED_WITH_REASON"
            ctx["phase_semantics"] = phase_semantics
            task.context = ctx
            flag_modified(task, 'context')

            await _emit_event(
                session, str(task.id), "phase.skipped", "system:triage", f"task:{task.id}",
                {"phase": phase, "reason": skip_reason, "execution_level": execution_level}, "info"
            )
            await session.commit()

            nxt = next_phase(phase)
            if not nxt:
                break
            phase = nxt
            task.status = phase
            task.progress = min(90, 10 + phases_done * 15)
            await session.flush()
            continue

        # 3. Determine Workers for Phase
        workers = allowed_workers_for_phase(
            phase,
            target_worker=task.worker_type,
            task_type=task.type,
            selected_workers=selected_workers_list,
        )
        workers = [w for w in workers if w in WORKER_REGISTRY]

        if not workers:
            logger.warning(f"Phase {phase}: no registered workers, advancing")
            phase_semantics[phase] = "AUTO_SATISFIED"
            ctx["phase_semantics"] = phase_semantics
            task.context = ctx
            flag_modified(task, 'context')

            nxt = next_phase(phase)
            if not nxt:
                break
            phase = nxt
            task.status = phase
            task.progress = min(90, 10 + phases_done * 15)
            await session.flush()
            continue

        logger.info(f"Task {task.id[:8]} phase={phase} (level={execution_level}) workers={workers}")
        phase_results = {}
        phase_semantics[phase] = "FULLY_EXECUTED"

        # ROOT-CAUSE FIX: commit the main session's pending writes (task
        # status/progress/root-event) BEFORE the worker gather. The gather runs
        # long LLM/subprocess calls (up to 120s+ per worker) and each worker
        # uses its OWN session, so holding this session's uncommitted write txn
        # open across the gather would keep the SQLite write lock for the whole
        # run — blocking every other request's write ("database is locked").
        # Release the lock now; post-merge task state is committed afterward.
        await session.commit()

        # WITH-PHASE PARALLELISM: Run all workers concurrently within the phase.
        # SESSION SAFETY: Each worker gets its own AsyncSession derived from the
        # executor session's bind (async_sessionmaker pattern from dispatcher/engine.py).
        # The main executor session remains for phase-level state transitions/commits.
        
        # P9 HOIST: Create ONE sessionmaker per phase instead of one per worker invocation
        from sqlalchemy.ext.asyncio import async_sessionmaker as worker_sessionmaker
        worker_factory = worker_sessionmaker(bind=session.bind, class_=AsyncSession, expire_on_commit=False)

        async def _execute_worker_in_new_session(wtype: str) -> tuple[str, dict]:
            """Execute a single worker with a dedicated session."""
            # Reuse the hoisted worker_factory (ONE per phase, not one per worker call)
            
            async with worker_factory() as worker_session:
                worker_cls = WORKER_REGISTRY.get(wtype)
                if not worker_cls:
                    return wtype, {
                        "result": {"success": False, "error": f"Worker {wtype} not registered"},
                        "verification_failed": False,
                        "fallback_used": False,
                        "event_target": f"worker:{wtype}:{phase}:{task.id}"
                    }

                lease = Lease(
                    task_id=task.id,
                    worker_id=f"worker-{wtype}",
                    worker_name=wtype.title(),
                    worker_type=wtype,
                    phase=phase,
                    status=LeaseStatus.ACTIVE.value,
                    created_at=_utcnow(),
                )
                worker_session.add(lease)

                started_event = await _emit_event(
                    worker_session, str(task.id), EventType.WORKER_STARTED.value, f"worker:{wtype}", f"task:{task.id}",
                    {"phase": phase, "task_title": task.title, "lease_phase": phase, "prev": prev_event_target}, "info"
                )

                # FIX: Broadcast worker.started to frontend for real-time Office Floor updates
                try:
                    from backend.routes.websocket import broadcast_worker_event
                    await broadcast_worker_event(
                        f"worker.{wtype}.started",
                        f"worker-{wtype}",
                        {
                            "title": task.title,
                            "phase": phase,
                        }
                    )
                except Exception as e:
                    logger.debug(f"Worker started broadcast failed: {e}")

                async def _reapply_started():
                    worker_session.add_all([lease, started_event])

                await _commit_with_lock_retry(worker_session, reapply=_reapply_started)

                worker_instance = worker_cls()
                worker_instance.agent_id = wtype
                worker_timeout = 120
                try:
                    from agents.context_assembly import get_model_config
                    _wcfg = get_model_config(wtype)
                    _base = int(_wcfg.get("timeout") or 120)
                    # Tool-calling workers run multi-round loops (each round = queue
                    # wait + LLM call + tool exec). A flat per-call budget is exhausted
                    # under parallel queueing, so scale the worker budget by tier so a
                    # worker's full tool loop is not killed prematurely.
                    _tier = str(_wcfg.get("tier") or "crafter").lower()
                    _mult = {"thinker": 2.5, "crafter": 2.5, "sprinter": 1.5}.get(_tier, 2.0)
                    worker_timeout = max(_base, int(_base * _mult))
                except Exception:
                    pass

                # Resolve worker skills and project memories dynamically
                active_worker_skills = []
                active_project_memories = []
                try:
                    from backend.skill_engine import resolve_skills_for_worker
                    from backend.memory_engine import retrieve_project_memories
                    active_worker_skills = await resolve_skills_for_worker(worker_session, wtype)
                    active_project_memories = await retrieve_project_memories(worker_session, str(task.project_id) if task.project_id else None)
                except Exception as e:
                    logger.debug(f"Skill/Memory resolution exception: {e}")

                # G1 FIX: resolve plugins assigned to this worker
                plugin_contexts = []
                try:
                    from backend.plugin_engine import resolve_plugins_for_worker
                    from backend.services.plugin_adapter import build_plugin_context
                    assigned_plugins = await resolve_plugins_for_worker(worker_session, wtype)
                    for p in assigned_plugins:
                        ppath = p.get("package_path", "")
                        if not ppath or not os.path.exists(ppath):
                            if p.get("is_required"):
                                plugin_contexts.append({
                                    "plugin_id": p.get("plugin_id"),
                                    "name": p.get("name"),
                                    "error": "Plugin package missing",
                                })
                            continue
                        pctx = build_plugin_context(ppath, p.get("components", []))
                        pctx["plugin_id"] = p.get("plugin_id")
                        pctx["name"] = p.get("name")
                        pctx["is_required"] = p.get("is_required")
                        instr = pctx.get("instructions", "")
                        if instr:
                            active_worker_skills.append(f"[Plugin: {p.get('name')}]\n{instr}")
                        for ai in pctx.get("agent_instructions", []):
                            if ai:
                                active_worker_skills.append(f"[Plugin Agent: {p.get('name')}]\n{ai}")
                        plugin_contexts.append(pctx)
                except Exception as e:
                    logger.debug(f"Plugin resolution exception: {e}")

                # FITUR 1: Query MCP Memory graph for task-relevant knowledge
                mcp_memory_context = []
                try:
                    from backend.services.mcp_service import mcp_service
                    from backend.database.session import AsyncSessionLocal
                    async with AsyncSessionLocal() as mcp_db:
                        mcp_schemas = await mcp_service.get_all_mcp_tool_schemas(mcp_db)
                        memory_tool_names = {"search_nodes", "read_graph", "open_nodes"}
                        has_memory_tools = any(t["name"] in memory_tool_names for t in mcp_schemas)
                        if has_memory_tools:
                            from backend.services.mcp_client import mcp_pool
                            search_keywords = f"{task.title} {task.description or ''}".split()[:5]
                            for keyword in search_keywords:
                                if len(keyword) < 3:
                                    continue
                                try:
                                    result = await mcp_pool.call_tool("search_nodes", {"query": keyword})
                                    content_parts = result.get("content", [])
                                    text = "\n".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
                                    if text and len(text) > 10:
                                        mcp_memory_context.append({"keyword": keyword, "memory": text[:500]})
                                        break
                                except Exception:
                                    pass
                            if mcp_memory_context:
                                active_project_memories.extend(mcp_memory_context)
                                logger.info(f"MCP memory: found {len(mcp_memory_context)} relevant memories for task {task.id[:8]}")
                except Exception as e:
                    logger.debug(f"MCP memory query exception (non-critical): {e}")

                # FITUR 2: Query lessons_learned table for company memory
                lessons_learned = []
                try:
                    from backend.database.session import AsyncSessionLocal
                    from storage.models import LessonLearned
                    from sqlalchemy import func, or_, and_, select
                    async with AsyncSessionLocal() as lesson_db:
                        q = select(LessonLearned).where(
                            or_(
                                LessonLearned.category.in_(["execution", "design", "security"]),
                                and_(LessonLearned.lesson.is_not(None), func.lower(LessonLearned.lesson).like(func.lower(f"%{task.type}%"))) if task.type else True
                            )
                        ).order_by(LessonLearned.created_at.desc()).limit(5)
                        result = await lesson_db.execute(q)
                        lessons = result.scalars().all()
                        lessons_learned = [
                            {
                                "lesson": l.lesson,
                                "category": l.category or "general",
                                "impact": l.impact or "medium",
                                "recommendation": l.recommendation or "",
                            }
                            for l in lessons
                        ]
                        if lessons_learned:
                            logger.info(f"Lessons learned: retrieved {len(lessons_learned)} for task {task.id[:8]} ({task.type or 'general'})")
                except ImportError:
                    pass
                except Exception as e:
                    logger.debug(f"Lessons learned query exception (non-critical): {e}")

                task_ctx = {
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description or "",
                    "type": task.type,
                    "repo_path": effective_repo_path,
                    "project_structure": project_structure,
                    "handoffs": handoffs_dict,
                    "skills": active_worker_skills,
                    "memories": active_project_memories,
                    "lessons_learned": lessons_learned,
                    "plugins": plugin_contexts,
                    "phase": phase,
                    "execution_level": execution_level,
                    "model_tier": ctx.get("model_tier"),
                }

                # A6: Build unified context from pipeline sources
                try:
                    from context.pipeline import ContextPipeline
                    from context.sources import CodeContextSource, ToolHistorySource

                    ctx_pipeline = ContextPipeline(token_budget=4000)
                    ctx_pipeline.add_source(CodeContextSource(config={"project_root": effective_repo_path}))
                    ctx_pipeline.add_source(ToolHistorySource(config={"recent_tool_calls": handoffs_dict}))
                    ctx_assembly = await ctx_pipeline.assemble(
                        f"{task.title} {task.description or ''}",
                        max_tokens=4000,
                    )
                    task_ctx["context_text"] = ctx_assembly.to_prompt_context()
                except Exception as ctx_err:
                    logger.debug(f"Context pipeline build failed (non-critical): {ctx_err}")

                from llm.provider import provider_manager
                active_profile = provider_manager.get_active_profile()
                if active_profile:
                    from runtime.adaptive import apply_worker_policy
                    task_ctx = apply_worker_policy(task_ctx, active_profile)

                # Initialize local flags
                verification_failed_local = False
                fallback_used_local = False
                worker_result = {}
                # Handoff payload for this worker, built locally and RETURNED to
                # the main loop (never written to the shared handoffs_dict/ctx/
                # task.context inside the worker) to avoid a lost-update race
                # across concurrent worker coroutines.
                worker_handoff = None
                # Holder for the terminal event created on the success OR
                # failure path, so the lock-retry can re-add it after rollback.
                final_event = None

                try:
                    result = await worker_instance.run_with_timeout(task_ctx, timeout=worker_timeout)
                    worker_result = {
                        "success": result.success,
                        "output": result.output[:1000] if result.output else "",
                        "error": result.error,
                        "used_fallback": bool(getattr(result, "used_fallback", False)),
                    }
                    if getattr(result, "used_fallback", False):
                        fallback_used_local = True

                    # Progressive Recovery Ladder (Attempts 1..4)
                    attempt = 1
                    while not result.success and attempt <= 4:
                        logger.warning(f"Worker {wtype} failed in {phase} — recovery attempt={attempt}")
                        try:
                            from backend.recovery_engine import RecoveryEngine
                            recovery = RecoveryEngine()
                            decision = recovery.evaluate_failure(
                                task_id=task.id,
                                phase=phase,
                                worker_type=wtype,
                                attempt=attempt,
                                error_msg=result.error or "unknown error",
                                previous_output=result.output or "",
                            )
                            recovery_event = Event(
                                type=EventType.WORKER_FAILED.value,
                                actor=f"recovery:{wtype}",
                                target=f"task:{task.id}",
                                data={
                                    "phase": phase,
                                    "strategy": decision.strategy,
                                    "attempt": attempt,
                                    "feedback": decision.feedback_prompt[:200],
                                },
                                severity="warn"
                            )
                            worker_session.add(recovery_event)

                            async def _reapply_recovery():
                                worker_session.add(recovery_event)

                            await _commit_with_lock_retry(worker_session, reapply=_reapply_recovery)

                            if not decision.should_proceed:
                                break
                            if decision.strategy == "ship_with_caveats":
                                # P11 FIX: surface caveats loudly instead of silently
                                # proceeding. Attach them to the worker result and emit
                                # a warning event so the UI/report can show them.
                                logger.warning(
                                    f"Worker {wtype} shipping with caveats: {decision.caveats}"
                                )
                                worker_result["ship_with_caveats"] = decision.caveats
                                caveat_event = Event(
                                    type=EventType.WORKER_COMPLETED.value,
                                    actor=f"recovery:{wtype}",
                                    target=f"task:{task.id}",
                                    data={
                                        "phase": phase,
                                        "strategy": "ship_with_caveats",
                                        "attempt": attempt,
                                        "caveats": decision.caveats,
                                    },
                                    severity="warn",
                                )
                                worker_session.add(caveat_event)

                                async def _reapply_caveat():
                                    worker_session.add(caveat_event)

                                await _commit_with_lock_retry(worker_session, reapply=_reapply_caveat)
                                break
                            if decision.strategy in ("retry", "refine_prompt", "fallback_model", "canonical_lock"):
                                task_ctx = {
                                    **task_ctx,
                                    "description": (
                                        f"{task.description or ''}\n\n"
                                        f"[RECOVERY attempt {attempt} strategy={decision.strategy}]\n"
                                        f"{decision.feedback_prompt}"
                                    ),
                                }
                                # Exponential backoff: avoid hammering the gateway with
                                # immediate retries (which cascade under parallel load).
                                # Skip in test mode (AIC_TESTING=1) — tests run with the
                                # LLM provider off and never hit a real gateway, so the
                                # 5/10/20s sleeps would make every worker recovery ~150s.
                                if os.environ.get("AIC_TESTING", "") != "1":
                                    _backoff = 5 * (2 ** (attempt - 1))  # 5s, 10s, 20s, ...
                                    await asyncio.sleep(_backoff)
                                result2 = await worker_instance.run_with_timeout(task_ctx, timeout=worker_timeout)
                                if result2.success:
                                    result = result2
                                    worker_result = {
                                        "success": True,
                                        "output": result.output[:1000] if result.output else "",
                                        "error": None,
                                        "recovered": True,
                                        "recovery_strategy": decision.strategy,
                                        "attempt": attempt,
                                        "used_fallback": bool(getattr(result, "used_fallback", False)),
                                    }
                                    if getattr(result, "used_fallback", False):
                                        fallback_used_local = True
                                    logger.info(f"Worker {wtype} succeeded after recovery {decision.strategy}")
                                    break
                                result = result2
                                attempt += 1
                                continue
                            break
                        except Exception as rec_err:
                            logger.error(f"Recovery engine error: {rec_err}")
                            break

                    lease.status = LeaseStatus.COMPLETED.value if result.success else LeaseStatus.FAILED.value
                    lease.exit_code = result.exit_code
                    lease.error_message = result.error if not result.success else None
                    lease.finished_at = _utcnow()

                    if phase == "verification" and not result.success:
                        verification_failed_local = True

                    from backend.workspace_manager import save_deliverable_file
                    from backend.code_extract import extract_code_blocks_to_workspace

                    doc_filename = f"{phase}/{wtype}-deliverable.md"
                    output_text = result.output if result.output else "(no output produced)"
                    doc_content = f"# Deliverable: {task.title}\n\n**Phase**: {phase.upper()}\n**Worker**: {wtype.title()}\n\n## Output\n\n{output_text}"
                    saved_path = await asyncio.to_thread(
                        save_deliverable_file, task.id, doc_filename, doc_content
                    )
                    lease.artifact_path = saved_path

                    if result.output and not getattr(result, "used_fallback", False):
                        extracted = await asyncio.to_thread(
                            extract_code_blocks_to_workspace, task.id, result.output,
                            effective_repo_path,
                        )
                        if extracted:
                            worker_result["extracted_files"] = extracted
                            logger.info(f"Extracted {len(extracted)} source files for task {task.id[:8]} (repo={effective_repo_path}): {extracted}")

                    if result.success and result.output:
                        # Build the handoff locally and rely on the main loop to
                        
                        # D1: Save key lessons/deliverables to durable project memory
                        try:
                            from backend.memory_engine import save_memory_entry
                            from datetime import timezone as tz
                            await save_memory_entry(
                                worker_session,
                                key=f"{phase}_{wtype}",
                                value=result.output[:1000],  # truncated for storage
                                project_id=task.project_id if hasattr(task, 'project_id') else effective_repo_path or None,
                                scope='project',
                                category='deliverable',
                                importance=0.85,
                            )
                            logger.info(f"Saved project memory entry [{phase}]_{wtype}")
                        except Exception as e:
                            logger.debug(f"Project memory save failed (non-critical): {e}")
                        # merge it after asyncio.gather returns, so concurrent
                        # worker coroutines never mutate the shared handoffs_dict
                        # / ctx / task.context (lost-update race).
                        worker_handoff = {
                            "worker": wtype,
                            "output": result.output[:1000],
                            "extracted": worker_result.get("extracted_files", []),
                        }

                    event_type = EventType.WORKER_COMPLETED.value if result.success else EventType.WORKER_FAILED.value
                    final_event = await _emit_event(
                        worker_session, str(task.id), event_type, f"worker:{wtype}", f"task:{task.id}",
                        {
                            "phase": phase,
                            "success": result.success,
                            "output": (result.output or "")[:200],
                            "lease_id": lease.id,
                            "prev": prev_event_target,
                            "used_fallback": bool(getattr(result, "used_fallback", False)),
                        },
                        "info" if result.success else "error"
                    )
                    
                    # FIX: Also broadcast worker.event to frontend for real-time Office Floor updates
                    try:
                        from backend.routes.websocket import broadcast_worker_event
                        await broadcast_worker_event(
                            f"worker.{wtype}.{event_type.split('.')[-1]}",  # Extract "completed" or "failed"
                            f"worker-{wtype}",
                            {
                                "title": task.title,
                                "phase": phase,
                                "success": result.success,
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Worker event broadcast failed: {e}")
                    
                except Exception as e:
                    worker_result = {"success": False, "error": str(e)}
                    lease.status = LeaseStatus.FAILED.value
                    lease.error_message = str(e)
                    lease.finished_at = _utcnow()
                    if phase == "verification":
                        verification_failed_local = True
                    
                    final_event = Event(
                        type=EventType.WORKER_FAILED.value,
                        actor=f"worker:{wtype}",
                        target=f"task:{task.id}",
                        data={"phase": phase, "error": str(e)[:300]},
                        severity="error"
                    )
                    worker_session.add(final_event)
                    logger.error(f"Worker {wtype} exception: {e}")

                # Snapshot the lease's terminal fields so a lock-retry can
                # re-apply them after rollback (rollback reverts in-memory attrs).
                _lease_terminal = {
                    "status": lease.status,
                    "exit_code": lease.exit_code,
                    "error_message": lease.error_message,
                    "finished_at": lease.finished_at,
                    "artifact_path": getattr(lease, "artifact_path", None),
                }

                async def _reapply_final():
                    for _k, _v in _lease_terminal.items():
                        setattr(lease, _k, _v)
                    if final_event is not None:
                        worker_session.add(final_event)

                await _commit_with_lock_retry(worker_session, reapply=_reapply_final)
                
                return wtype, {
                    "result": worker_result,
                    "verification_failed": verification_failed_local,
                    "fallback_used": fallback_used_local,
                    "event_target": f"worker:{wtype}:{phase}:{task.id}",
                    "handoff": worker_handoff,
                }

        # Execute all workers concurrently with return_exceptions=True
        # so one failure doesn't cancel others
        worker_tasks = [_execute_worker_in_new_session(wtype) for wtype in workers]
        worker_responses = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Merge results deterministically by processing responses in order
        phase_verification_failed = False
        phase_fallback_used = False
        
        for idx, response in enumerate(worker_responses):
            wtype = workers[idx]
            
            # Handle exception results from gather(return_exceptions=True)
            if isinstance(response, BaseException):
                phase_results[wtype] = {"success": False, "error": f"Worker crash: {str(response)}"}
                logger.error(f"Worker {wtype} raised unhandled exception: {response}")
                continue
            
            try:
                worker_type_result, meta = response
                phase_results[worker_type_result] = meta["result"]
                if meta.get("verification_failed"):
                    phase_verification_failed = True
                if meta.get("fallback_used"):
                    phase_fallback_used = True
                # Merge handoffs sequentially (after the gather) so concurrent
                # worker coroutines never mutate the shared handoffs_dict/ctx/
                # task.context. Last-writer-wins per phase key is accepted.
                handoff = meta.get("handoff")
                if handoff is not None:
                    handoffs_dict[phase] = handoff
                    ctx["handoffs"] = handoffs_dict
                    task.context = ctx
                    flag_modified(task, 'context')
            except Exception as merge_err:
                logger.error(f"Failed to merge worker {wtype} result: {merge_err}")
                phase_results[wtype] = {"success": False, "error": f"Merge error: {merge_err}"}

        # Handle phase-level flags
        if phase_verification_failed:
            verification_failed = phase_verification_failed
        if phase_fallback_used:
            fallback_used = phase_fallback_used

        results[phase] = phase_results
        phases_done += 1

        # Commit the main session to ensure it sees changes from worker sessions
        # (leases created in worker sessions need to be visible to the main session)
        await session.commit()

        # 4. Local Repair Loop for Verification Failures
        if phase == "verification" and verification_failed:
            repair_history = ctx.get("repairs", [])
            repair_attempts = len(repair_history)
            if repair_attempts < 3:
                repair_attempts += 1
                logger.warning(f"Task {task.id[:8]} verification failed — entering Local Repair Loop (attempt {repair_attempts}/3)")
                
                # Determine responsible implementation worker
                responsible_worker = task.worker_type if task.worker_type in ("backend", "frontend", "coding", "database") else "backend"
                
                await _emit_event(
                    session, str(task.id), "local_repair.started", "system:repair", f"task:{task.id}",
                    {"attempt": repair_attempts, "responsible_worker": responsible_worker}, "warn"
                )
                await session.commit()

                # Re-run responsible worker with verification feedback
                repair_worker_cls = WORKER_REGISTRY.get(responsible_worker)
                if repair_worker_cls:
                    r_worker = repair_worker_cls()
                    r_worker.agent_id = responsible_worker
                    repair_task_ctx = {
                        "task_id": task.id,
                        "title": task.title,
                        "description": (
                            f"{task.description or ''}\n\n"
                            f"[LOCAL REPAIR ATTEMPT {repair_attempts}]\n"
                            f"Verification phase failed. Please fix bugs in generated code artifacts."
                        ),
                        "type": task.type,
                        "repo_path": effective_repo_path,
                        "project_structure": project_structure,
                        "phase": "implementation",
                        "execution_level": execution_level,
                        "model_tier": ctx.get("model_tier"),
                    }
                    r_res = await r_worker.run_with_timeout(repair_task_ctx, timeout=_adaptive_worker_timeout(r_worker.worker_type))
                    if r_res.output and not getattr(r_res, "used_fallback", False):
                        await asyncio.to_thread(
                            extract_code_blocks_to_workspace, task.id, r_res.output,
                            effective_repo_path,
                        )

                # Re-run QA worker for targeted re-verification
                qa_cls = WORKER_REGISTRY.get("qa")
                if qa_cls:
                    qa_worker = qa_cls()
                    qa_worker.agent_id = "qa"
                    qa_task_ctx = {
                        "task_id": task.id,
                        "title": task.title,
                        "description": task.description or "",
                        "type": task.type,
                        "repo_path": effective_repo_path,
                        "phase": "verification",
                        "execution_level": execution_level,
                        "model_tier": ctx.get("model_tier"),
                    }
                    qa_res = await qa_worker.run_with_timeout(qa_task_ctx, timeout=_adaptive_worker_timeout(qa_worker.worker_type))
                    if qa_res.success:
                        verification_failed = False
                        logger.info(f"Task {task.id[:8]} LOCAL REPAIR SUCCEEDED on attempt {repair_attempts}")
                        repair_history.append({"attempt": repair_attempts, "outcome": "success", "worker": responsible_worker})
                        ctx["repairs"] = repair_history
                        task.context = ctx
                        flag_modified(task, 'context')
                        await _emit_event(
                            session, str(task.id), "local_repair.completed", "system:repair", f"task:{task.id}",
                            {"attempt": repair_attempts, "outcome": "success"}, "info"
                        )
                        await session.commit()
                    else:
                        repair_history.append({"attempt": repair_attempts, "outcome": "failed", "worker": responsible_worker})
                        ctx["repairs"] = repair_history
                        task.context = ctx
                        flag_modified(task, 'context')

            # 5. Dynamic Escalation if repair fails
            if verification_failed and execution_level in (ExecutionLevel.QUICK.value, ExecutionLevel.STANDARD.value):
                new_level = ExecutionLevel.EXTENDED.value if execution_level == ExecutionLevel.QUICK.value else ExecutionLevel.FULL.value
                logger.warning(f"Task {task.id[:8]} DYNAMIC ESCALATION: {execution_level} -> {new_level}")
                escalations = ctx.get("escalations", [])
                escalations.append({"from": execution_level, "to": new_level, "reason": "Local repair loop failed after 3 attempts"})
                ctx["escalations"] = escalations
                ctx["execution_level"] = new_level
                task.context = ctx
                flag_modified(task, 'context')

                await _emit_event(
                    session, str(task.id), "task.escalated", "system:triage", f"task:{task.id}",
                    {"from_level": execution_level, "to_level": new_level, "reason": "Local repair loop failed"}, "warn"
                )
                await session.commit()
                execution_level = new_level

        # Approval Gate
        if phase == "planning" and task.approval_required:
            ap_result = await session.execute(
                select(Approval).where(
                    Approval.task_id == task.id,
                    Approval.status == ApprovalStatus.PENDING.value,
                ).limit(1)
            )
            pending = ap_result.scalar_one_or_none()
            if not pending:
                ap_done = await session.execute(
                    select(Approval).where(
                        Approval.task_id == task.id,
                        Approval.status == ApprovalStatus.APPROVED.value,
                    ).limit(1)
                )
                approved = ap_done.scalar_one_or_none()
                if not approved:
                    pending = Approval(
                        task_id=task.id,
                        type="phase_advance",
                        status=ApprovalStatus.PENDING.value,
                        requested_by="system:executor",
                        reason=f"Planning complete for task '{task.title}' — human approval required before implementation",
                    )
                    session.add(pending)
                    session.add(Event(
                        type=EventType.APPROVAL_REQUESTED.value,
                        actor="system:governance",
                        target=f"task:{task.id}",
                        data={"phase": "planning", "type": "phase_advance"},
                        severity="warn",
                    ))
                    await session.commit()

            if pending and pending.status == ApprovalStatus.PENDING.value:
                task.status = "planning"
                task.progress = min(90, 10 + phases_done * 15)
                await session.commit()
                return {
                    "success": False,
                    "phases": phases_done,
                    "results": results,
                    "waiting_for_approval": True,
                    "fallback_used": fallback_used,
                    "execution_level": execution_level,
                }

        # Advance to next phase
        nxt = next_phase(phase)
        if not nxt:
            break
        phase = nxt
        task.status = phase
        task.progress = min(90, 10 + phases_done * 15)

        await _emit_event(
            session, str(task.id), EventType.PHASE_ADVANCED.value, "system:fsm", f"task:{task.id}",
            {"phase": phase, "progress": task.progress, "prev": prev_event_target, "execution_level": execution_level}, "info"
        )
        await session.commit()

    # 6. Completion Integrity
    block_reason = None

    # FITUR 2 Lapis 3: Taste checker — scan deliverable text for AI-isms during closeout
    taste_findings = []
    try:
        from backend.services.taste_checker import scan_text
        for phase_name, phase_results in results.items():
            for worker_name, worker_result in phase_results.items():
                if worker_name in ("documentation", "pm", "rex", "research", "qa"):
                    output = worker_result.get("output", "")
                    if output and len(output) > 50:
                        findings = scan_text(output)
                        if findings:
                            taste_findings.extend([
                                {"phase": phase_name, "worker": worker_name, **f.to_dict()}
                                for f in findings
                            ])
        if taste_findings:
            ctx["taste_findings"] = taste_findings
            task.context = ctx
            flag_modified(task, 'context')
            logger.info(f"Task {task.id[:8]} taste checker: {len(taste_findings)} findings (reported, not blocking)")
    except Exception as taste_err:
        logger.debug(f"Taste checker exception (non-critical): {taste_err}")

    if verification_failed:
        block_reason = "verification_failed"
    elif fallback_used:
        block_reason = "llm_fallback_output"
    else:
        from backend.workspace_manager import list_workspace_files
        from shared.workspace import sandbox_workspace_dir
        
        # Check deliverable workspace (secondary signal)
        files = list_workspace_files(task.id)
        deliverable_source_files = [
            f for f in files
            if f.get("extension") in ("py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "css", "html", "sql")
        ]
        
        # Check actual workspace/sandbox where write_file tools wrote real source files (primary)
        scope_id = (task.context or {}).get("conversation_id") or task.id
        workspace_root = effective_repo_path  # This is the sandbox or project repo where files were actually written
        source_files_in_workspace = []
        if os.path.exists(workspace_root):
            for root, _, filenames in os.walk(workspace_root):
                for fname in filenames:
                    if fname.endswith(tuple([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".css", ".html", ".sql"])):
                        full_p = Path(root) / fname
                        try:
                            rel_p = str(full_p.relative_to(workspace_root))
                            # Skip virtual environments and node_modules
                            if "/node_modules/" in rel_p or "/venv/" in rel_p or "/.venv/" in rel_p:
                                continue
                            source_files_in_workspace.append(fname)
                        except ValueError:
                            pass
        
        has_source_artifacts = bool(source_files_in_workspace) or bool(deliverable_source_files)
        
        if task.type in ("feature", "bugfix", "refactor") and not has_source_artifacts:
            if "implementation" in results and phase_semantics.get("implementation") == "FULLY_EXECUTED":
                block_reason = "no_source_artifacts"

    ctx["phase_semantics"] = phase_semantics
    task.context = ctx
    flag_modified(task, 'context')

    if block_reason:
        task.status = TaskStatus.FAILED.value
        task.progress = max(0, task.progress - 10)
        task.error_message = f"Completion blocked: {block_reason}"
        ctx["phase_results"] = results
        ctx["phases_completed"] = phases_done
        ctx["completion_blocked"] = block_reason
        ctx["fallback_used"] = fallback_used
        task.context = ctx
        flag_modified(task, 'context')

        await _emit_event(
            session, str(task.id), EventType.WORKER_FAILED.value, "system:integrity", f"task:{task.id}",
            {"action": "completion_blocked", "reason": block_reason, "phases_completed": phases_done}, "error"
        )
        
        # WP-07: Autonomy Engine error recovery hook
        try:
            from autonomy.engine import AutonomyEngine
            autonomy_engine = AutonomyEngine(session)
            await autonomy_engine.detect_anomaly(
                anomaly_type="task_failure",
                severity="high",
                description=f"Task {task.id[:8]} failed: {block_reason}",
                affected_component="runtime_executor",
            )
            logger.info(f"Autonomy Engine: anomaly recorded for task {task.id[:8]}")
        except Exception as auto_err:
            logger.warning(f"Autonomy Engine hook failed (non-critical): {auto_err}")
        
        await session.commit()
        return {
            "success": False,
            "phases": phases_done,
            "results": results,
            "verification_failed": verification_failed,
            "fallback_used": fallback_used,
            "completion_blocked": block_reason,
            "execution_level": execution_level,
        }

    # Mark Complete
    task.status = TaskStatus.COMPLETED.value
    task.progress = 100
    task.completed_at = _utcnow()
    ctx["phase_results"] = results
    ctx["phases_completed"] = phases_done
    ctx["fallback_used"] = False
    ctx["golden_path"] = {"execution_level": execution_level, "phases_completed": phases_done, "verification": "passed"}
    task.context = ctx
    flag_modified(task, 'context')

    await _emit_event(
        session, str(task.id), EventType.TASK_COMPLETED.value, "system:dispatcher", f"task:{task.id}",
        {"phases_completed": phases_done, "execution_level": execution_level, "golden_path": "complete"}, "info"
    )
    
    # WP-04: Verification Engine hook after task completion
    verification_state = "skipped"
    try:
        from verification.engine import VerificationEngine
        verification_engine = VerificationEngine(session)
        # Get brief_id from task context if available
        brief_id = ctx.get("brief_id", "")
        if brief_id:
            verification_result = await verification_engine.verify(
                brief_id=brief_id,
                task_results=results,
            )
            logger.info(f"Verification result: {verification_result.state}")
            verification_state = verification_result.state
            ctx["verification_state"] = verification_state
            task.context = ctx
            flag_modified(task, 'context')
    except Exception as verify_err:
        logger.warning(f"Verification Engine hook failed (non-critical): {verify_err}")
    
    # WP-06: Delivery Engine hook after verification
    if verification_state == "passed":
        try:
            from delivery.engine import DeliveryEngine
            delivery_engine = DeliveryEngine(session)
            brief_id = ctx.get("brief_id", "")
            plan_id = ctx.get("plan_id", "")
            graph_id = ctx.get("graph_id", "")
            if brief_id:
                delivery_report = await delivery_engine.generate_report(
                    brief_id=brief_id,
                    plan_id=plan_id,
                    graph_id=graph_id,
                    task_results=results,
                )
                logger.info(f"Delivery report generated: {delivery_report.brief_id}")
                ctx["delivery_report_id"] = delivery_report.brief_id
                task.context = ctx
                flag_modified(task, 'context')
        except Exception as delivery_err:
            logger.warning(f"Delivery Engine hook failed (non-critical): {delivery_err}")
    
    await session.commit()

    logger.info(f"Task {task.id[:8]} completed (level={execution_level}) — {phases_done} phases done")
    return {"success": True, "phases": phases_done, "results": results, "fallback_used": False, "execution_level": execution_level}
