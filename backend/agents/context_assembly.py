"""AIC Platform — Agent Context Assembly.

Builds runtime context for worker LLM calls using the agent registry.
Combines:
- Agent soul (core purpose, philosophy, anti-patterns)
- Operating constraints (quality bar, evidence standards)
- Phase-specific instructions
- Prior worker handoffs & deliverables
- Task-relevant skill guidelines
- Durable project memory
- Tool permissions
"""
from typing import Optional

from agents.registry import AGENT_REGISTRY, AgentDefinition


# Domain/task-type to skill mapping rules
SKILL_MAP = {
    "feature": "api-completeness-audit: Audit backend/frontend completeness against commercial standards.",
    "bugfix": "systematic-debugging: 4-phase root cause debugging — understand bugs before fixing.",
    "test": "test-driven-development: Enforce RED-GREEN-REFACTOR and comprehensive test coverage.",
    "refactor": "simplify-code: Clean up recent code changes, eliminate boilerplate, enforce PonyTail simplicity.",
    "security": "security-audit: Comprehensive security audit — authentication, authorization, secret handling.",
    "docs": "llm-wiki: Author clear, interlinked markdown documentation.",
    "infra": "server-health-monitoring: Monitor system health, containers, process readiness.",
}


def assemble_system_prompt(agent_id: str, task_context: dict, phase: str, project_context: Optional[dict] = None) -> str:
    """Build the full system prompt for an agent's LLM call."""
    agent = AGENT_REGISTRY.get(agent_id)
    if not agent:
        return f"You are a {agent_id} worker. Execute the task as specified."

    parts = [agent.soul.system_prompt]

    # 1. Operating Constraints
    parts.append(f"\n--- OPERATING CONSTRAINTS ---")
    parts.append(f"Quality bar: {agent.soul.quality_bar}")
    parts.append(f"Evidence standards: {agent.soul.evidence_standards}")
    parts.append(f"Anti-patterns (DO NOT): {agent.soul.anti_patterns}")
    
    # Additional philosophical guidance (not always critical, but informs deeper decisions)
    parts.append(f"\n--- ENGINEERING PHILOSOPHY ---")
    parts.append(agent.soul.engineering_philosophy)
    
    parts.append(f"\n--- RISK PHILOSOPHY ---")
    parts.append(agent.soul.risk_philosophy)

    parts.append(f"\n--- COLLABORATION & ESCALATION ---")
    parts.append(f"Collaboration style: {agent.soul.collaboration_style}")
    parts.append(f"Escalation policy: {agent.soul.escalation_policy}")

    # 2. Phase-Specific Guidance
    parts.append(f"\n--- CURRENT PHASE: {phase.upper()} ---")
    phase_hints = {
        "discovery": "Analyze the request. If anything is ambiguous, flag what needs clarification. Produce a summary of understood requirements.",
        "investigate": "Investigate the requirements. Produce analysis, research findings, and requirement specifications.",
        "planning": "Design the architecture. If the task is complex, include a '## Subtask Decomposition' section with numbered subtasks, each specifying Worker, Depends on, and Description.",
        "implementation": "Implement the actual code. Write working, tested code with proper error handling and file path annotations.",
        "verification": "Verify deliverables exist and are correct. Check code syntax. Cross-check against requirements. Report PASS or FAIL with evidence.",
        "closeout": "Finalize deliverables. Ensure README, REQUIREMENTS, and documentation are present and accurate.",
    }
    if phase.lower() in phase_hints:
        parts.append(phase_hints[phase.lower()])

    # 3. Tool Permissions
    parts.append(f"\n--- ALLOWED TOOLS ---")
    parts.append(f"You may use: {', '.join(agent.tools.allowed)}")
    if agent.tools.prohibited:
        parts.append(f"You may NOT: {', '.join(agent.tools.prohibited)}")

    # 4. Task Context
    parts.append(f"\n--- TASK ---")
    parts.append(f"Title: {task_context.get('title', 'N/A')}")
    parts.append(f"Description: {task_context.get('description', 'N/A')[:500]}")
    parts.append(f"Execution Level: {task_context.get('execution_level', 'STANDARD')}")

    # 5. Prior Worker Handoffs Protocol
    handoffs = task_context.get("handoffs") or {}
    if handoffs:
        parts.append(f"\n--- PRIOR WORKER HANDOFFS ---")
        for h_phase, h_data in list(handoffs.items())[-3:]:
            w_name = h_data.get("worker", "worker")
            output_snippet = (h_data.get("output") or "")[:400]
            parts.append(f"[{h_phase.upper()} — {w_name}]:\n{output_snippet}\n")

    # 6. Task-Relevant Skill Guidelines
    active_skills = task_context.get("skills")
    if active_skills and isinstance(active_skills, list):
        parts.append(f"\n--- TASK-RELEVANT SKILLS ---")
        for s in active_skills[:5]:
            parts.append(f"• {s}")
    else:
        task_type = task_context.get("type", "feature")
        if task_type in SKILL_MAP:
            parts.append(f"\n--- TASK-RELEVANT SKILLS ---")
            parts.append(SKILL_MAP[task_type])

    # 7. Durable Project Memory
    active_memories = task_context.get("memories")
    if active_memories and isinstance(active_memories, list):
        parts.append(f"\n--- DURABLE PROJECT MEMORY ---")
        for m in active_memories[:5]:
            parts.append(f"• [{m.get('category', 'decision').upper()}] {m.get('key')}: {m.get('value')}")
    else:
        memory_notes = task_context.get("memory") or (project_context.get("memory") if project_context else None)
        if memory_notes:
            parts.append(f"\n--- DURABLE PROJECT MEMORY ---")
            parts.append(str(memory_notes)[:300])

    # 8. Adaptive Runtime Policy
    adaptive = task_context.get("adaptive_runtime")
    if adaptive:
        parts.append(f"\n--- ADAPTIVE RUNTIME POLICY ---")
        parts.append(f"Context classification: {adaptive.get('context', {}).get('classification')}")
        parts.append(f"Planning depth: {adaptive.get('worker', {}).get('planning_depth')}")
        parts.append(f"Prompt detail: {adaptive.get('worker', {}).get('prompt_detail')}")
        parts.append(f"Verification frequency: {adaptive.get('worker', {}).get('verification_frequency')}")
        parts.append(f"Checkpoint strategy: {adaptive.get('checkpoint_strategy')}")
        parts.append(f"Max parallel workers: {adaptive.get('worker', {}).get('max_parallel_workers')}")

    # 8b. Worker Tuning Policy (per-worker defaults when no adaptive runtime)
    else:
        t = agent.tuning
        parts.append(f"\n--- WORKING MODE ---")
        parts.append(f"Planning depth: {t.planning_depth} | Verification: {t.verification_frequency} | Checkpoints: {t.checkpoint_strategy} | Prompt detail: {t.prompt_detail}")

    # 8c. Lessons Learned — company memory from past executions
    lessons = task_context.get("lessons_learned")
    if lessons and isinstance(lessons, list):
        parts.append(f"\n--- LESSONS LEARNED (from past company work) ---")
        for l in lessons[:5]:
            rec = l.get("recommendation") or ""
            parts.append(f"• [{(l.get('category') or 'general').upper()}] {l.get('lesson', '')}" + (f" → {rec}" if rec else ""))

    # 9. Project Structure Context
    if project_context:
        parts.append(f"\n--- PROJECT CONTEXT ---")
        for k, v in list(project_context.items())[:5]:
            parts.append(f"{k}: {str(v)[:200]}")

    return "\n".join(parts)


def get_model_config(agent_id: str) -> dict:
    """Get model/provider config for an agent."""
    agent = AGENT_REGISTRY.get(agent_id)
    if not agent:
        return {"tier": "crafter", "temperature": 0.3, "timeout": 120, "max_retries": 1}
    return {
        "tier": agent.model.tier,
        "temperature": agent.model.temperature,
        "timeout": agent.model.timeout,
        "max_retries": agent.model.max_retries,
    }
