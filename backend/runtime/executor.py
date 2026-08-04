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
import os
import logging
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
    raw_repo_path = str(project_obj.repo_path) if project_obj and project_obj.repo_path else "."
    effective_repo_path = raw_repo_path if (raw_repo_path != "." and os.path.exists(raw_repo_path)) else "."
    project_structure = inspect_project_structure(effective_repo_path) if effective_repo_path != "." else {}

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

        for wtype in workers:
            worker_cls = WORKER_REGISTRY.get(wtype)
            if not worker_cls:
                continue

            # Policy gate: check if this worker is allowed to execute
            from policy.engine import policy, Decision
            policy_result = policy.evaluate(
                action="worker.execute",
                worker_type=wtype,
                resource=f"task:{task.id}",
                context={"phase": phase, "task_type": task.type},
            )
            if policy_result and hasattr(policy_result, 'decision') and policy_result.decision == Decision.DENY:
                logger.warning(f"Policy denied worker {wtype}: {policy_result.reason}")
                phase_results[wtype] = {"success": False, "error": f"Policy denied: {policy_result.reason}"}
                continue

            lease = Lease(
                task_id=task.id,
                worker_id=f"worker-{wtype}",
                worker_name=wtype.title(),
                worker_type=wtype,
                phase=phase,
                status=LeaseStatus.ACTIVE.value,
                created_at=_utcnow(),
            )
            session.add(lease)

            await _emit_event(
                session, str(task.id), EventType.WORKER_STARTED.value, f"worker:{wtype}", f"task:{task.id}",
                {"phase": phase, "task_title": task.title, "lease_phase": phase, "prev": prev_event_target}, "info"
            )
            await session.commit()

            worker = worker_cls()
            worker.agent_id = wtype
            worker_timeout = 120
            try:
                from agents.context_assembly import get_model_config
                worker_timeout = int(get_model_config(wtype).get("timeout") or 120)
            except Exception:
                pass

            # Resolve worker skills and project memories dynamically
            active_worker_skills = []
            active_project_memories = []
            try:
                from backend.skill_engine import resolve_skills_for_worker
                from backend.memory_engine import retrieve_project_memories
                active_worker_skills = await resolve_skills_for_worker(session, wtype)
                active_project_memories = await retrieve_project_memories(session, str(task.project_id) if task.project_id else None)
            except Exception as e:
                logger.debug(f"Skill/Memory resolution exception: {e}")

            # G1 FIX: resolve plugins assigned to this worker and build adapted
            # context so plugin commands/tools/agents are available in the
            # company batch runtime (mirrors agent_runner.py plugin resolution).
            plugin_contexts = []
            try:
                from backend.plugin_engine import resolve_plugins_for_worker
                from backend.services.plugin_adapter import build_plugin_context
                assigned_plugins = await resolve_plugins_for_worker(session, wtype)
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
                    # Surface instructions into the skills channel so the worker
                    # system prompt (assemble_system_prompt) picks them up.
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
                    # Check if memory server tools are available
                    memory_tool_names = {"search_nodes", "read_graph", "open_nodes"}
                    has_memory_tools = any(t["name"] in memory_tool_names for t in mcp_schemas)
                    if has_memory_tools:
                        # Query MCP memory via search_nodes with task keywords
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
                                    break  # one good match is enough
                            except Exception:
                                pass
                        if mcp_memory_context:
                            active_project_memories.extend(mcp_memory_context)
                            logger.info(f"MCP memory: found {len(mcp_memory_context)} relevant memories for task {task.id[:8]}")
            except Exception as e:
                logger.debug(f"MCP memory query exception (non-critical): {e}")

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
                "plugins": plugin_contexts,
                "phase": phase,
                "execution_level": execution_level,
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

            try:
                result = await worker.run_with_timeout(task_ctx, timeout=worker_timeout)
                phase_results[wtype] = {
                    "success": result.success,
                    "output": result.output[:1000] if result.output else "",
                    "error": result.error,
                    "used_fallback": bool(getattr(result, "used_fallback", False)),
                }
                if getattr(result, "used_fallback", False):
                    fallback_used = True

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
                        session.add(Event(
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
                        ))
                        await session.commit()

                        if not decision.should_proceed:
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
                            result2 = await worker.run_with_timeout(task_ctx, timeout=worker_timeout)
                            if result2.success:
                                result = result2
                                phase_results[wtype] = {
                                    "success": True,
                                    "output": result.output[:1000] if result.output else "",
                                    "error": None,
                                    "recovered": True,
                                    "recovery_strategy": decision.strategy,
                                    "attempt": attempt,
                                    "used_fallback": bool(getattr(result, "used_fallback", False)),
                                }
                                if getattr(result, "used_fallback", False):
                                    fallback_used = True
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
                    verification_failed = True
                    logger.error(f"VERIFICATION FAILED: {wtype}")

                from backend.workspace_manager import save_deliverable_file
                from backend.code_extract import extract_code_blocks_to_workspace

                doc_filename = f"{phase}/{wtype}-deliverable.md"
                doc_content = f"# Deliverable: {task.title}\n\n**Phase**: {phase.upper()}\n**Worker**: {wtype.title()}\n\n## Output\n\n{result.output or 'Execution complete.'}"
                saved_path = save_deliverable_file(task.id, doc_filename, doc_content)
                lease.artifact_path = saved_path

                if result.output and not getattr(result, "used_fallback", False):
                    extracted = extract_code_blocks_to_workspace(task.id, result.output, repo_path=effective_repo_path)
                    if extracted:
                        phase_results[wtype]["extracted_files"] = extracted
                        logger.info(f"Extracted {len(extracted)} source files for task {task.id[:8]} (repo={effective_repo_path}): {extracted}")

                if result.success and result.output:
                    handoffs_dict[phase] = {
                        "worker": wtype,
                        "output": result.output[:1000],
                        "extracted": phase_results[wtype].get("extracted_files", []),
                    }
                    ctx["handoffs"] = handoffs_dict
                    task.context = ctx
                    flag_modified(task, 'context')

                event_type = EventType.WORKER_COMPLETED.value if result.success else EventType.WORKER_FAILED.value
                await _emit_event(
                    session, str(task.id), event_type, f"worker:{wtype}", f"task:{task.id}",
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
                prev_event_target = f"worker:{wtype}:{phase}:{task.id}"
            except Exception as e:
                phase_results[wtype] = {"success": False, "error": str(e)}
                lease.status = LeaseStatus.FAILED.value
                lease.error_message = str(e)
                lease.finished_at = _utcnow()
                if phase == "verification":
                    verification_failed = True

                session.add(Event(
                    type=EventType.WORKER_FAILED.value,
                    actor=f"worker:{wtype}",
                    target=f"task:{task.id}",
                    data={"phase": phase, "error": str(e)[:300], "prev": prev_event_target},
                    severity="error"
                ))
                logger.error(f"Worker {wtype} exception: {e}")

            await session.commit()

        results[phase] = phase_results
        phases_done += 1

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
                    }
                    r_res = await r_worker.run_with_timeout(repair_task_ctx, timeout=120)
                    if r_res.output and not getattr(r_res, "used_fallback", False):
                        extract_code_blocks_to_workspace(task.id, r_res.output, repo_path=effective_repo_path)

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
                        "repo_path": ".",
                        "phase": "verification",
                        "execution_level": execution_level,
                    }
                    qa_res = await qa_worker.run_with_timeout(qa_task_ctx, timeout=120)
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
        files = list_workspace_files(task.id)
        source_files = [
            f for f in files
            if f.get("extension") in ("py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "css", "html", "sql")
        ]
        if task.type in ("feature", "bugfix", "refactor") and not source_files:
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
