"""AIC Platform — Worker Runtime.

Base worker class and full worker registry (15 worker types).
Each worker has a role, system prompt, and execution strategy.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import asyncio
import logging
import shutil
import sys

from backend.services.content_utils import truncate_content

logger = logging.getLogger("aic.workers")


async def _llm_or_fallback(worker, user_prompt, tier, temperature, purpose, fallback, task_context=None, phase=None):
    """Call the active LLM provider.

    Returns (content, meta) where meta has:
      used_fallback: bool
      reason: optional str
      model/provider when real LLM succeeded
    Template fallback is NEVER silent success — caller must mark used_fallback.
    """
    import re
    from llm.provider import provider_manager, ModelTier

    meta = {"used_fallback": False, "reason": None, "model": None, "provider": None}

    # P1 #6: get_active() may return a provider with an empty api_key →
    # "Illegal header value b'Bearer '". get_active_with_key() prefers a
    # provider with a usable key (mirrors agent_runner.py / tool_chat_service.py).
    provider = provider_manager.get_active_with_key()
    if not provider:
        logger.warning(f"{getattr(worker, 'name', worker)} no active LLM provider — fallback")
        meta["used_fallback"] = True
        meta["reason"] = "no_provider"
        return fallback, meta

    # Canonical agent id = worker_type (not "{type}-worker" display name)
    agent_id = getattr(worker, "agent_id", None) or getattr(worker, "worker_type", None)
    system_prompt = getattr(worker, "SYSTEM_PROMPT", None)
    model_cfg = {"timeout": 120, "temperature": temperature, "tier": tier}
    if agent_id:
        try:
            from agents.context_assembly import assemble_system_prompt, get_model_config
            ctx = task_context or {"title": purpose, "description": truncate_content(user_prompt, 200)}
            system_prompt = assemble_system_prompt(agent_id, ctx, phase or "execution")
            model_cfg = get_model_config(agent_id)
            if model_cfg.get("temperature") is not None:
                temperature = model_cfg["temperature"]
            # Task-level model_tier override (e.g. "vision") wins over the
            # agent's registry tier so a task can be launched with vision.
            if task_context and task_context.get("model_tier"):
                model_cfg["tier"] = task_context["model_tier"]
            if model_cfg.get("tier"):
                # ModelTier enum or string both accepted by provider.chat
                tier_map = {
                    "thinker": ModelTier.THINKER,
                    "crafter": ModelTier.CRAFTER,
                    "sprinter": ModelTier.SPRINTER,
                    "system": ModelTier.SPRINTER,
                    "vision": ModelTier.VISION,
                }
                t = model_cfg["tier"]
                if isinstance(t, str) and t in tier_map:
                    tier = tier_map[t]
                elif isinstance(t, ModelTier):
                    tier = t
                else:
                    tier = t
        except ImportError:
            pass

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    # Vision hook: when the task context carries an image (image_url or
    # image_data_url), build OpenAI multimodal parts instead of a plain string
    # so a vision-tier worker can actually analyze the image.
    image_data_url = None
    if task_context:
        image_data_url = task_context.get("image_data_url") or task_context.get("image_url")
    if image_data_url:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        })
    else:
        messages.append({"role": "user", "content": user_prompt})

    timeout = int(model_cfg.get("timeout") or 120)
    try:
        result = await asyncio.wait_for(
            provider_manager.chat(messages=messages, tier=tier, temperature=temperature, purpose=purpose),
            timeout=timeout,
        )
        content = (result.get("content") or "").strip()
        if content:
            for tag in ("thinking", "thought", "reason"):
                content = re.sub(rf'<{tag}>.*?</{tag}>', '', content, flags=re.DOTALL).strip()
            if content.startswith("Thinking."):
                parts = content.split("\n\n", 1)
                if len(parts) > 1 and len(parts[0]) > 50:
                    content = parts[1].strip()
        raw_msg = (result.get("raw") or {}).get("choices", [{}])[0].get("message", {})
        reasoning = ""
        if isinstance(raw_msg, dict):
            reasoning = raw_msg.get("reasoning_content") or raw_msg.get("reasoning") or ""
        if reasoning and not content:
            content = reasoning
        if content and len(content) > 20:
            meta["model"] = result.get("model")
            meta["provider"] = getattr(getattr(provider, "config", None), "name", None)
            return content, meta
        meta["used_fallback"] = True
        meta["reason"] = "empty_content"
        return fallback, meta
    except Exception as e:
        logger.warning(f"{getattr(worker, 'name', worker)} LLM call failed ({purpose}): {e} — using template")
        meta["used_fallback"] = True
        meta["reason"] = f"error:{type(e).__name__}:{e}"
        return fallback, meta


from llm.provider import ModelTier as _MT
_THINKER = _MT.THINKER
_CRAFTER = _MT.CRAFTER
_SPRINTER = _MT.SPRINTER


async def _llm_with_tools(worker, user_prompt, tier, temperature, purpose, fallback,
                           tool_executor, task_context=None, phase=None, max_rounds=10):
    """Multi-turn tool-use loop. Calls LLM with tool definitions, executes tool_calls,
    appends results, and repeats until the LLM returns text or max_rounds is reached.

    Returns (content, meta, tool_calls_list).
    """
    import json as _json
    from llm.provider import provider_manager, ModelTier

    meta = {"used_fallback": False, "reason": None, "model": None, "provider": None}

    # P1 #6: get_active() may return a provider with an empty api_key →
    # "Illegal header value b'Bearer '". Mirror agent_runner.py / tool_chat_service.py.
    provider = provider_manager.get_active_with_key()
    if not provider:
        meta["used_fallback"] = True
        meta["reason"] = "no_provider"
        return fallback, meta, []

    agent_id = getattr(worker, "agent_id", None) or getattr(worker, "worker_type", None)
    system_prompt = getattr(worker, "SYSTEM_PROMPT", None)
    model_cfg = {"timeout": 120, "temperature": temperature, "tier": tier}
    if agent_id:
        try:
            from agents.context_assembly import assemble_system_prompt, get_model_config
            ctx = task_context or {"title": purpose, "description": truncate_content(user_prompt, 200)}
            system_prompt = assemble_system_prompt(agent_id, ctx, phase or "execution")
            model_cfg = get_model_config(agent_id)
            if model_cfg.get("temperature") is not None:
                temperature = model_cfg["temperature"]
            # Task-level model_tier override (e.g. "vision") wins over the
            # agent's registry tier so a task can be launched with vision.
            if task_context and task_context.get("model_tier"):
                model_cfg["tier"] = task_context["model_tier"]
            if model_cfg.get("tier"):
                # ModelTier enum or string both accepted by provider.chat
                tier_map = {
                    "thinker": ModelTier.THINKER,
                    "crafter": ModelTier.CRAFTER,
                    "sprinter": ModelTier.SPRINTER,
                    "system": ModelTier.SPRINTER,
                    "vision": ModelTier.VISION,
                }
                t = model_cfg["tier"]
                if isinstance(t, str) and t in tier_map:
                    tier = tier_map[t]
                elif isinstance(t, ModelTier):
                    tier = t
                else:
                    tier = t
        except ImportError:
            pass

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    # Vision hook: when the task context carries an image (image_url or
    # image_data_url), build OpenAI multimodal parts instead of a plain string
    # so a vision-tier worker can actually analyze the image.
    image_data_url = None
    if task_context:
        image_data_url = task_context.get("image_data_url") or task_context.get("image_url")
    if image_data_url:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        })
    else:
        messages.append({"role": "user", "content": user_prompt})

    tools_schema = tool_executor.to_openai_schema()

    # Filter tools based on agent registry permissions
    agent_id_for_tools = getattr(worker, "agent_id", None) or getattr(worker, "worker_type", None)
    if agent_id_for_tools:
        try:
            from agents.registry import AGENT_REGISTRY
            agent_def = AGENT_REGISTRY.get(agent_id_for_tools)
            if agent_def and hasattr(agent_def, 'tools'):
                tp = agent_def.tools
                if tp and hasattr(tp, 'allowed') and tp.allowed:
                    allowed_names = set(tp.allowed)
                    tools_schema = [t for t in tools_schema if t.get("function", {}).get("name") in allowed_names]
        except ImportError:
            pass

    # Inject MCP tools if available
    try:
        from backend.services.mcp_service import mcp_service
        from backend.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as mcp_db:
            mcp_schemas = await mcp_service.get_all_mcp_tool_schemas(mcp_db)
            for mcp_tool in mcp_schemas:
                tools_schema.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp_{mcp_tool['name']}",
                        "description": mcp_tool.get("description", ""),
                        "parameters": mcp_tool.get("inputSchema", {"type": "object", "properties": {}}),
                    },
                })
    except Exception:
        pass  # MCP optional

    timeout = int(model_cfg.get("timeout") or 120)
    all_tool_calls = []

    for round_num in range(max_rounds):
        try:
            result = await asyncio.wait_for(
                provider_manager.chat(
                    messages=messages, tier=tier, temperature=temperature,
                    purpose=purpose, tools=tools_schema,
                ),
                timeout=timeout,
            )
        except Exception as e:
            logger.warning(f"{getattr(worker, 'name', worker)} LLM call failed ({purpose}) round {round_num}: {e}")
            meta["used_fallback"] = True
            meta["reason"] = f"error:{type(e).__name__}:{e}"
            return fallback, meta, all_tool_calls

        raw_msg = (result.get("raw") or {}).get("choices", [{}])[0].get("message", {})
        if not isinstance(raw_msg, dict):
            raw_msg = {}

        tool_calls = raw_msg.get("tool_calls")
        if tool_calls:
            meta["model"] = result.get("model")
            meta["provider"] = getattr(getattr(provider, "config", None), "name", None)
            # Append assistant message with tool_calls
            assistant_msg = {"role": "assistant", "content": raw_msg.get("content") or ""}
            assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                try:
                    fn_args = _json.loads(fn.get("arguments", "{}"))
                except _json.JSONDecodeError:
                    fn_args = {}

                # Execute the tool
                if fn_name.startswith("mcp_"):
                    # MCP tool execution
                    real_tool_name = fn_name[4:]  # Remove "mcp_" prefix
                    from backend.services.mcp_client import mcp_pool
                    try:
                        mcp_result = await mcp_pool.call_tool(real_tool_name, fn_args)
                        content_parts = mcp_result.get("content", [])
                        result_content = "\n".join(p.get("text", "") for p in content_parts if p.get("type") == "text") or _json.dumps(mcp_result)
                    except Exception as e:
                        result_content = f"MCP error: {e}"
                else:
                    tool_method = getattr(tool_executor, fn_name, None)
                    if tool_method:
                        # FIX: bound every tool call so a hanging tool (e.g. a
                        # shell command that backgrounds a process and holds the
                        # pipe open) can never stall the worker loop forever.
                        # The wait_for cancellation triggers the tool's own
                        # process-group kill on timeout.
                        try:
                            tc_result = await asyncio.wait_for(
                                tool_method(**fn_args), timeout=120
                            )
                        except asyncio.TimeoutError:
                            result_content = (
                                f"Tool '{fn_name}' timed out after 120s "
                                f"(possible backgrounded process holding the pipe open)"
                            )
                        else:
                            result_content = tc_result.output if hasattr(tc_result, "output") else str(tc_result)
                    else:
                        result_content = f"Error: unknown tool '{fn_name}'"

                all_tool_calls.append({"name": fn_name, "args": fn_args, "result": result_content[:2000]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result_content[:4000],
                })
            continue  # Next round

        # No tool_calls — final text response
        content = (result.get("content") or "").strip()
        if content:
            import re
            for tag in ("thinking", "thought", "reason"):
                content = re.sub(rf'<{tag}>.*?</{tag}>', '', content, flags=re.DOTALL).strip()
            if content.startswith("Thinking."):
                parts = content.split("\n\n", 1)
                if len(parts) > 1 and len(parts[0]) > 50:
                    content = parts[1].strip()

        reasoning = raw_msg.get("reasoning_content") or raw_msg.get("reasoning") or ""
        if reasoning and not content:
            content = reasoning

        if content and len(content) > 20:
            meta["model"] = result.get("model")
            meta["provider"] = getattr(getattr(provider, "config", None), "name", None)
            return content, meta, all_tool_calls

        meta["used_fallback"] = True
        meta["reason"] = "empty_content"
        return fallback, meta, all_tool_calls

    # Exhausted rounds
    meta["used_fallback"] = True
    meta["reason"] = "max_tool_rounds"
    return fallback, meta, all_tool_calls


class WorkerResult:
    """Result of worker execution."""
    def __init__(self, success: bool, exit_code: int = 0, artifact_path: str | None = None,
                 output: str = "", error: str | None = None, used_fallback: bool = False,
                 llm_meta: dict | None = None, tool_calls: list | None = None,
                 todos: list | None = None, file_diffs: list | None = None):
        self.success = success
        self.exit_code = exit_code
        self.artifact_path = artifact_path
        self.output = output
        self.error = error
        self.used_fallback = used_fallback
        self.llm_meta = llm_meta or {}
        self.tool_calls = tool_calls or []
        self.todos = todos or []
        self.file_diffs = file_diffs or []


def _result_from_llm(content: str, meta: dict, tool_calls=None) -> WorkerResult:
    """Map LLM helper output to WorkerResult. Fallback is never silent success."""
    if meta.get("used_fallback"):
        return WorkerResult(
            success=False,
            exit_code=2,
            output=content or "",
            error=f"LLM_FALLBACK:{meta.get('reason') or 'unknown'}",
            used_fallback=True,
            llm_meta=meta,
            tool_calls=tool_calls or [],
        )
    return WorkerResult(success=True, output=content, used_fallback=False, llm_meta=meta, tool_calls=tool_calls or [])


def _make_permission_checker(worker_type: str):
    """Create a permission checker callable for a worker type."""
    from backend.services.tool_permissions import check_tool_permission
    def checker(tool_name: str) -> bool:
        return check_tool_permission(worker_type, tool_name)
    return checker


class BaseWorker(ABC):
    """Abstract base for all workers."""
    SYSTEM_PROMPT = "You are an AI worker in the AIC Platform. Be precise and thorough."

    def __init__(self, worker_type: str = "generic", config: dict | None = None, **kwargs):
        self.worker_type = kwargs.get("worker_type") or worker_type
        self.agent_id = self.worker_type  # canonical AGENT_REGISTRY key
        self.config = config or {}
        self.name = f"{self.worker_type}-worker"

    @abstractmethod
    async def execute(self, task_context: dict) -> WorkerResult:
        ...

    async def run_with_timeout(self, task_context: dict, timeout: int = 600) -> WorkerResult:
        try:
            return await asyncio.wait_for(self.execute(task_context), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Worker {self.name} timed out after {timeout}s")
            return WorkerResult(success=False, exit_code=124, error=f"Timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Worker {self.name} failed: {e}")
            return WorkerResult(success=False, exit_code=1, error=str(e))


# ── 15 Worker Implementations (AIC Skill Canonical) ────

class PMWorker(BaseWorker):
    """Project Manager — orchestrates task lifecycle: investigation, planning, closeout."""
    SYSTEM_PROMPT = "You are Aria, the Product Manager — the OWNER of docs/PRD.md, the single source of truth for requirements. WORKFLOW: (1) Read docs/PRD.md (the discovery draft). (2) FINALIZE the PRD: fill gaps with sound product judgment or mark them explicitly as unresolved questions; assign priority (P0/P1/P2) to every functional requirement; sharpen every acceptance criterion so it is testable; resolve ambiguities where the brief is unclear. PRESERVE all original requirements while enriching and structuring — never silently drop a requirement. Replace the DRAFT status line with 'Status: FINAL — approved by PM'. (3) Write the finalized PRD back to docs/PRD.md via write_file. (4) Then produce docs/PROJECT_PLAN.md: milestones, a task breakdown derived from the PRD, suggested worker assignments, and a definition-of-done checklist. You write documentation only — never source code."

    def __init__(self, config=None, **kwargs):
        super().__init__("pm", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        task_type = task_context.get("type", "feature")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # PM produces the PRD/requirements docs: docs-scoped write_file
            # (documentation paths only), never shell (role/tool enforcement).
            allowed_tools=["read_file", "explore", "search", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Implementation Plan\n\n"
            f"## Task: {title}\n\n"
            f"## Analysis\nTask type: {task_type}\nDescription: {description}\n\n"
            f"## Approach\n1. Analyze requirements\n2. Design solution\n3. Implement\n4. Test\n5. Review\n\n"
            f"## Acceptance Criteria\n- Implementation matches requirements\n- Tests pass\n- Code review approved\n"
        )
        plan, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Task: {title}\nType: {task_type}\nDescription: {description}",
            _THINKER, 0.3, "planner", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=plan,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class ArchitectWorker(BaseWorker):
    """Designs system architecture and component interactions."""
    SYSTEM_PROMPT = "You are Atlas, the Architect. You design system architecture, component interactions, and data flow. You break complex work into subtasks with clear worker assignments and dependencies. You work during planning phase. Produce docs/ARCHITECTURE.md with the design using the write_file tool (documentation artifacts only); you do not write source code. Your output MUST include a '## Subtask Decomposition' section with numbered subtasks, each specifying: Worker, Depends on, and Description. Break work into 2-5 subtasks when the task is complex."

    def __init__(self, config=None, **kwargs):
        super().__init__("architect", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # Architect produces ARCHITECTURE.md / technical specs: docs-scoped
            # write_file (documentation paths only), never shell.
            allowed_tools=["explore", "read_file", "search", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Architecture Design\n\n## Task: {title}\n\n"
            f"## Components\n- API Layer\n- Business Logic\n- Data Layer\n\n"
            f"## Data Flow\nRequest -> Controller -> Service -> Repository -> Database\n\n"
            f"## Decision\nUse existing patterns. No new dependencies.\n\n"
            f"## Subtask Decomposition\n"
            f"## Subtask 1: Backend API\n- Worker: backend\n- Depends on: none\n- Description: Create API endpoints\n\n"
            f"## Subtask 2: Frontend UI\n- Worker: frontend\n- Depends on: Backend API\n- Description: Build UI components\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Design architecture for: {title}\n{description}\n\nIMPORTANT: Include a '## Subtask Decomposition' section with numbered subtasks. For each subtask, specify:\n- Worker: (backend/frontend/database/qa/security/designer/architect/documentation)\n- Depends on: (names of subtasks this depends on, or 'none')\n- Description: (what this subtask should accomplish)\n\nBreak the work into 2-5 subtasks with clear dependencies.",
            _THINKER, 0.3, "architect", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class ResearchWorker(BaseWorker):
    """Researches solutions, finds patterns, evaluates approaches."""
    SYSTEM_PROMPT = "You are Sage, the Researcher. You find facts, evaluate trade-offs, and validate assumptions. You read documentation, analyze options, and provide evidence-based recommendations. Write your findings to docs/RESEARCH.md using the write_file tool (documentation artifacts only). You NEVER write source code — implementation belongs to backend/frontend/coding workers. Your output is structured research with sources, trade-offs, and clear recommendations."

    def __init__(self, config=None, **kwargs):
        super().__init__("research", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # Research produces RESEARCH.md artifacts: docs-scoped write_file
            # (documentation paths only), never shell.
            allowed_tools=["explore", "read_file", "search", "web_fetch", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Research Report\n\n## Topic: {title}\n\n"
            f"## Findings\n- Existing patterns identified\n- Standard approach recommended\n\n"
            f"## Recommendation\nUse established patterns. Minimize custom code.\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Research: {title}\n{description}",
            _THINKER, 0.3, "research", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class CodingWorker(BaseWorker):
    """General-purpose coding worker — delegating to OpenCode or LLM BackendWorker."""
    SYSTEM_PROMPT = "You are a senior software engineer. Write clean, tested, production-quality code."

    def __init__(self, config=None, **kwargs):
        super().__init__("coding", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
        )
        prompt = (
            f"Implement: {title}\n{description}\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "1. Produce REAL runnable source code, not only design prose.\n"
            "2. For each file, use fenced blocks with path annotation.\n"
            "3. Prefer a minimal complete project: app module + tests + requirements if needed.\n"
            "4. Do not invent secrets. Use placeholders only.\n"
            "5. Use the available tools (read_file, write_file, shell, explore, search) to inspect the workspace and create files.\n"
        )
        template = (
            f"# Implementation\n\n## Task: {title}\n\n"
            f"## Components\n- Source code\n- Tests\n- Configuration\n\n"
            f"## Quality\n- Clean code\n- Error handling\n- Documentation\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self, prompt,
            _CRAFTER, 0.5, "coding", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class FrontendWorker(BaseWorker):
    """Handles frontend/UI implementation (React, CSS, components)."""
    SYSTEM_PROMPT = "You are Leo, the Frontend Engineer. Implement UIs, components, client-side logic. FIRST: read docs/PRD.md, docs/DESIGN.md if present to match requirements/design. Write clean, accessible, responsive source code matching specs. No docs (that's the docs worker)."

    def __init__(self, config=None, **kwargs):
        super().__init__("frontend", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
        )
        prompt = (
            f"Build frontend for: {title}\n{description}\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "1. Produce REAL source files, not only component descriptions.\n"
            "2. Annotate each fenced block with a file path, e.g.:\n"
            "```tsx src/App.tsx\n...\n```\n"
            "3. Include enough files for a minimal runnable UI when applicable.\n"
            "4. Use the available tools (read_file, write_file, shell, explore, search) to inspect the workspace and create files.\n"
        )
        template = (
            f"# Frontend Implementation\n\n## Task: {title}\n\n"
            f"## Components\n- React component with TypeScript\n- Tailwind CSS styling\n- Error/loading states\n\n"
            f"## Accessibility\n- Semantic HTML\n- Keyboard navigation\n- ARIA labels\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self, prompt,
            _CRAFTER, 0.3, "frontend", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class BackendWorker(BaseWorker):
    """Handles backend/API implementation (routes, services, validation)."""
    SYSTEM_PROMPT = "You are Hugo, the Backend Engineer. Implement server-side logic, APIs, DB schemas, data processing. FIRST: read docs/PRD.md, docs/ARCHITECTURE.md, docs/DESIGN.md if present to understand requirements/design. Write clean, correct, testable source code. No docs (that's the docs worker)."

    def __init__(self, config=None, **kwargs):
        super().__init__("backend", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
        )
        prompt = (
            f"Build backend for: {title}\n{description}\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "1. Produce REAL runnable source code, not only design prose.\n"
            "2. For each file, use fenced blocks with path annotation, e.g.:\n"
            "```python app.py\n# code here\n```\n"
            "```python tests/test_app.py\n# tests here\n```\n"
            "3. Prefer a minimal complete project: app module + tests + requirements if needed.\n"
            "4. Do not invent secrets. Use placeholders only.\n"
            "5. Use the available tools (read_file, write_file, shell, explore, search) to inspect the workspace and create files.\n"
        )
        template = (
            f"# Backend Implementation\n\n## Task: {title}\n\n"
            f"## API Design\n- RESTful endpoints\n- Input validation\n- Error handling\n- Auth checks\n\n"
            f"## Data Layer\n- SQLAlchemy models\n- Async queries\n- Transaction safety\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self, prompt,
            _CRAFTER, 0.3, "backend", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class DatabaseWorker(BaseWorker):
    """Handles database schema, migrations, and queries."""
    SYSTEM_PROMPT = "You are Nova, the Data Engineer. You design database schemas, data models, and persistence strategies. You ensure data integrity through constraints and proper typing. Your output is valid SQL schema with constraints and indexes."

    def __init__(self, config=None, **kwargs):
        super().__init__("database", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            allowed_tools=["read_file", "write_file", "shell"],
        )
        template = (
            f"# Database Changes\n\n## Task: {title}\n\n"
            f"## Schema\n- Columns defined\n- Indexes optimized\n- Constraints enforced\n\n"
            f"## Migration\n- Non-destructive\n- Reversible\n- Tested\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Database work for: {title}\n{description}",
            _CRAFTER, 0.3, "database", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


# REVIEWWORKER REMOVED — redundant with QA; no FSM phase schedules it



class TestingWorker(BaseWorker):
    """QA Engineer & Bug Hunter (Eve). Executes tests, verifies deliverables, and conducts structured bug audits."""
    SYSTEM_PROMPT = "You are Eve, the QA Engineer & Bug Hunter. DUAL ROLE: (1) QA VERIFICATION — verify deliverables by inspecting actual workspace files, checking code syntax, running tests, and cross-checking against requirements; verify results against the acceptance criteria in docs/PRD.md and write pass/fail results to docs/QA_REPORT.md via the write_file tool (pass/fail summary, coverage notes, issues found). (2) BUG AUDIT — when tasked with a bug hunt, conduct a structured audit: investigate by reading files, searching codebases, and exploring directory structures; run shell commands only for testing diagnostics (existing test frameworks); do NOT modify source code under any circumstances; write findings to docs/BUG_REPORT.md via write_file with an Executive Summary, Findings with severity (CRITICAL/HIGH/MEDIUM/LOW), location and description per finding, evidence snippets, suspected root cause, reproducible steps, and concrete recommendations; prioritize by severity. You are SKEPTICAL. You try to find problems. You NEVER rubber-stamp. Never guess—always read actual errors or logs. You do not write source code. Your verification result determines whether the task can be completed."

    def __init__(self, config=None, **kwargs):
        super().__init__("qa", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        # Bug-hunt tasks: Eve switches to Bug Hunter mode — an LLM-driven
        # structured audit producing docs/BUG_REPORT.md (read-only investigation).
        if task_context.get("type") == "bughunt":
            return await self._run_bug_audit(task_context)
        return await self._run_verification(task_context)

    async def _run_bug_audit(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        # Bug audit is read-only investigation + docs-scoped report writing,
        # with shell allowed only for running existing test diagnostics.
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            allowed_tools=["read_file", "search", "shell", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Bug Report\n\n## Task: {title}\n\n"
            f"## Scope\n{description}\n\n"
            f"## Findings\nUnder investigation\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Bug audit: {title}\n{description}",
            _THINKER, 0.2, "qa", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )

    async def _run_verification(self, task_context: dict) -> WorkerResult:
        import os
        from backend.workspace_manager import get_task_workspace_dir
        task_id = task_context.get("task_id", "")
        repo_path = task_context.get("repo_path", ".")
        output_lines = ["# Test Results\n"]
        tests_passed = True

        # Check task workspace for deliverables to verify
        workspace = str(get_task_workspace_dir(task_id))
        # get_task_workspace_dir() auto-creates the dir, so probe for actual
        # content (an empty workspace falls through to repo-based testing).
        if os.path.exists(workspace) and os.listdir(workspace):
            # Count deliverable files as basic verification
            deliverables = []
            for root, dirs, files in os.walk(workspace):
                for f in files:
                    if f.endswith(('.md', '.py', '.js', '.ts', '.tsx', '.json')):
                        deliverables.append(os.path.relpath(os.path.join(root, f), workspace))
            output_lines.append(f"## Deliverable Verification\nFound {len(deliverables)} files in workspace:")
            for d in deliverables[:10]:
                output_lines.append(f"- {d}")

            # Check if REQUIREMENTS.md exists
            if os.path.exists(os.path.join(workspace, "REQUIREMENTS.md")):
                output_lines.append("\n## Requirements Check\n- REQUIREMENTS.md: PRESENT")
            else:
                output_lines.append("\n## Requirements Check\n- REQUIREMENTS.md: MISSING")
                tests_passed = False

            # Check if README.md exists
            if os.path.exists(os.path.join(workspace, "README.md")):
                output_lines.append("- README.md: PRESENT")
            else:
                output_lines.append("- README.md: MISSING")

            # Try to verify Python code if present
            py_files = [f for f in deliverables if f.endswith('.py')]
            if py_files:
                output_lines.append(f"\n## Python Code Verification\nFound {len(py_files)} Python files")
                # Basic syntax check
                for pf in py_files[:3]:
                    full = os.path.join(workspace, pf)
                    try:
                        with open(full) as f:
                            compile(f.read(), pf, 'exec')
                        output_lines.append(f"- {pf}: syntax OK")
                    except SyntaxError as e:
                        output_lines.append(f"- {pf}: SYNTAX ERROR: {e}")
                        tests_passed = False

            # Check for test files
            test_files = [f for f in deliverables if 'test' in f.lower()]
            if test_files:
                output_lines.append(f"\n## Test Files\nFound {len(test_files)} test files")
            else:
                output_lines.append("\n## Test Files\nNo dedicated test files found — recommendation: add tests")
                # Don't fail just because no tests exist — that's a recommendation

            output_lines.append(f"\n## Verification Result\n{'PASSED' if tests_passed else 'FAILED'}")
        else:
            # Fall back to repo_path-based testing
            if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "pyproject.toml")):
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pytest", "--tb=short", "-q",
                    cwd=repo_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                except asyncio.TimeoutError:
                    # H2: kill the timed-out subprocess so it doesn't leak as an orphan.
                    proc.kill()
                    stdout, _ = await proc.communicate()
                    tests_passed = False
                    output_lines.append(f"\n**FAILED** — pytest timed out after 120s (process killed)")
                output_lines.append(f"```\n{stdout.decode()}\n```")
                if proc.returncode != 0:
                    tests_passed = False
                    output_lines.append(f"\n**FAILED** (exit {proc.returncode})")
                else:
                    output_lines.append("\n**PASSED**")
            elif os.path.exists(os.path.join(repo_path, "package.json")):
                npm_path = shutil.which("npm")
                if npm_path:
                    proc = await asyncio.create_subprocess_exec(
                        npm_path, "test", "--", "--watchAll=false",
                        cwd=repo_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    try:
                        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                    except asyncio.TimeoutError:
                        # H2: kill the timed-out subprocess so it doesn't leak as an orphan.
                        proc.kill()
                        stdout, _ = await proc.communicate()
                        tests_passed = False
                        output_lines.append(f"\n**FAILED** — npm test timed out after 120s (process killed)")
                    output_lines.append(f"```\n{stdout.decode()}\n```")
                    if proc.returncode != 0:
                        tests_passed = False
                else:
                    output_lines.append("\n**SKIPPED** — npm not found in PATH")
            else:
                output_lines.append("\n**SKIPPED** - no test framework detected; verification pending")
                tests_passed = False  # M5 FIX: honest SKIPPED, not PASSED for a fresh sandbox

        # Write QA report to workspace docs/ (docs-scoped artifact). Best-effort.
        try:
            from workers.tools import ToolExecutor
            from backend.services.tool_permissions import check_tool_permission
            qa_report = (
                "# QA Report\n\n"
                f"## Task: {task_context.get('title', '')}\n\n"
                f"## Result: {'PASSED' if tests_passed else 'FAILED'}\n\n"
                "## Summary\n" + "\n".join(output_lines[1:]) + "\n\n"
                "## Notes\n"
                "- Run pytest/npm for full coverage.\n"
                "- Address any SYNTAX ERROR or MISSING requirements before closeout.\n"
            )
            qa_executor = ToolExecutor(
                workspace_root=str(get_task_workspace_dir(task_id)),
                permission_checker=lambda tn: check_tool_permission("qa", tn),
                allowed_tools=["read_file", "search", "shell", "write_file"],
                write_scope="docs",
            )
            await qa_executor.write_file("docs/QA_REPORT.md", qa_report)
        except Exception:
            pass  # Non-critical: test result still drives success/failure

        return WorkerResult(success=tests_passed, exit_code=0 if tests_passed else 1,
                           output="\n".join(output_lines), error=None if tests_passed else "Verification failed — deliverables incomplete or syntax errors found")


class SecurityWorker(BaseWorker):
    """Performs security analysis and vulnerability scanning."""
    SYSTEM_PROMPT = "You are Sentinel, the Security Engineer. Perform security audits, threat modeling, vulnerability analysis. Think like an attacker. Check path traversal, injection, XSS, secrets, input validation. NEVER rubber-stamp. Write findings to docs/SECURITY_AUDIT.md via write_file (docs-scoped): vulnerabilities found, severity, fixes. No source code."

    def __init__(self, config=None, **kwargs):
        super().__init__("security", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # Security produces SECURITY_AUDIT.md reports: docs-scoped
            # write_file (documentation paths only), never shell.
            allowed_tools=["read_file", "search", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Security Analysis\n\n## Task: {title}\n\n"
            f"## Checks\n- Input validation: PASS\n- SQL injection: PASS\n"
            f"- XSS prevention: PASS\n- Auth bypass: PASS\n- Secrets exposure: PASS\n\n"
            f"## Verdict: SECURE\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Security review: {title}\n{description}",
            _CRAFTER, 0.2, "security", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class DocumentationWorker(BaseWorker):
    """Writes and updates documentation."""
    SYSTEM_PROMPT = "You are Echo, the Documentation Engineer. Produce accurate, useful documentation from source files and deliverables. Write docs/README.md via write_file (docs-scoped): overview, features, prerequisites, installation, running, testing, project structure. Verify all instructions work. No fabrication."

    def __init__(self, config=None, **kwargs):
        super().__init__("documentation", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # Documentation writes README/guides: docs-scoped write_file
            # (documentation paths only), never shell (role/tool enforcement).
            allowed_tools=["read_file", "write_file", "explore", "search"],
            write_scope="docs",
        )
        template = (
            f"# Documentation\n\n## Task: {title}\n\n"
            f"## Overview\n{description}\n\n"
            f"## Usage\nRefer to API docs at /api/docs\n\n"
            f"## Examples\nSee test files for usage patterns.\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Document: {title}\n{description}",
            _SPRINTER, 0.2, "documentation", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class DeploymentWorker(BaseWorker):
    """Handles build and deployment validation.

    NOTE: The 'deployment' alias resolves to the flint Infrastructure Engineer
    persona defined in AGENT_REGISTRY['flint']. This class exists for routing
    compatibility while flint provides the canonical identity and behavior."""
    SYSTEM_PROMPT = "You are Flint, the Infrastructure Engineer. You design deployment configurations, CI/CD pipelines, and infrastructure. You ensure reliability, observability, and safe deployment. Your output is infrastructure-as-code with deployment configs and CI pipelines."

    def __init__(self, config=None, **kwargs):
        super().__init__("flint", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            allowed_tools=["read_file", "write_file", "shell"],
        )
        template = (
            f"# Deployment Validation\n\n## Task: {title}\n\n"
            f"## Build Status\n- Dockerfile: checked\n- Health check: configured\n\n"
            f"## Readiness: READY\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Validate deployment: {title}\n{description}",
            _CRAFTER, 0.3, "deployment", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class DevOpsWorker(BaseWorker):
    """Handles CI/CD, infrastructure, and operational concerns.

    NOTE: The 'devops' alias resolves to the nexus Integration Engineer persona
    defined in AGENT_REGISTRY['nexus']. This class exists for routing compatibility
    while nexus provides the canonical identity and behavior."""
    SYSTEM_PROMPT = "You are Nexus, the Integration Engineer. You ensure components integrate correctly. You identify integration points, define interfaces, and verify cross-component behavior. Your output is integration analysis and interface specifications."

    def __init__(self, config=None, **kwargs):
        super().__init__("nexus", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            allowed_tools=["read_file", "write_file", "shell"],
        )
        template = (
            f"# Integration Analysis\n\n## Task: {title}\n\n"
            f"## Interfaces\n- Component contracts defined\n- Data formats specified\n- Error propagation agreed\n\n"
            f"## Contract Tests\n- Interface assertions listed\n- Boundary cases covered\n\n"
            f"## Dependencies\n- External APIs identified\n- Third-party services mapped\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Integration analysis for: {title}\n{description}",
            _CRAFTER, 0.3, "devops", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


class PerformanceWorker(BaseWorker):
    """Analyzes and optimizes performance."""
    SYSTEM_PROMPT = "You are Pulse, the Performance Engineer. Measure performance, identify bottlenecks. NEVER guess. Profile, measure, report actual data. Write results to docs/PERFORMANCE_REPORT.md via write_file (docs-scoped): response times, memory/CPU usage, optimization recommendations. No source code."

    def __init__(self, config=None, **kwargs):
        super().__init__("performance", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        from workers.tools import ToolExecutor
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        workspace = task_context.get("workspace") or task_context.get("repo_path") or ""
        tool_executor = ToolExecutor(
            workspace_root=workspace,
            permission_checker=_make_permission_checker(self.worker_type),
            # Performance produces PERFORMANCE_REPORT.md: docs-scoped write_file
            # (documentation paths only), never shell.
            allowed_tools=["read_file", "write_file"],
            write_scope="docs",
        )
        template = (
            f"# Performance Analysis\n\n## Task: {title}\n\n"
            f"## Metrics\n- Response time: acceptable\n- Memory usage: normal\n- CPU: normal\n\n"
            f"## Optimizations\n- No critical issues found\n"
        )
        result, _llm_meta, tool_calls = await _llm_with_tools(self,
            f"Performance review: {title}\n{description}",
            _SPRINTER, 0.1, "performance", template, tool_executor,
            task_context=task_context)
        return WorkerResult(
            success=not _llm_meta.get("used_fallback"),
            output=result,
            error=f"LLM_FALLBACK:{_llm_meta.get('reason')}" if _llm_meta.get("used_fallback") else None,
            used_fallback=_llm_meta.get("used_fallback", False),
            llm_meta=_llm_meta,
            tool_calls=tool_calls,
            file_diffs=[d.to_dict() for d in tool_executor.file_diffs],
        )


# ── Worker Registry ────────────────────────────────────

class DesignerWorker(BaseWorker):
    """Creates UI/UX designs, component specifications, and visual architecture."""
    SYSTEM_PROMPT = "You are Luna, the Designer. You create UI specifications, component designs, and design system guidelines. You focus on user experience, accessibility, and consistency. You work during planning phase to produce specs that frontend engineers implement. Write the design spec to docs/DESIGN.md using the write_file tool (documentation artifacts only); you do not write source code — frontend engineers implement it. Your output includes component descriptions, interaction states, and accessibility requirements."

    def __init__(self, config=None, **kwargs):
        super().__init__("designer", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        template = (
            f"# Design Specification\n\n## Task: {title}\n\n"
            f"## Visual Architecture\n- Component hierarchy defined\n- Layout system specified\n\n"
            f"## Design Tokens\n- Color palette\n- Typography scale\n- Spacing system\n\n"
            f"## Accessibility\n- WCAG 2.1 AA compliance\n- Keyboard navigation\n"
        )
        from workers.tools import ToolExecutor
        from backend.services.tool_permissions import check_tool_permission
        repo_path = task_context.get("repo_path", "")
        # THINKER role: designer produces specs — read-only tools only, never
        # write_file/shell (role/tool enforcement).
        # Designer produces DESIGN.md / design specs: docs-scoped write_file
        # (documentation paths only), never shell.
        tool_executor = ToolExecutor(
            workspace_root=repo_path,
            permission_checker=lambda tn: check_tool_permission("designer", tn),
            allowed_tools=["explore", "read_file", "search", "write_file"],
            write_scope="docs",
        )
        content, meta, tool_calls = await _llm_with_tools(self,
            f"Design spec for: {title}\n{description}",
            _CRAFTER, 0.4, "designer", template, task_context=task_context, tool_executor=tool_executor)
        return _result_from_llm(content, meta, tool_calls=tool_calls)


class GovernorWorker(BaseWorker):
    """Compliance gatekeeper and final closeout evaluator."""
    SYSTEM_PROMPT = "You are Rex, the Governor. You are the compliance gatekeeper. Your job is to verify that deliverables are complete, tests exist, documentation is present, and quality standards are met. You NEVER auto-approve. You inspect actual files, cross-check against requirements, and report findings honestly. Write your governance verdict to docs/COMPLIANCE.md via the write_file tool: approval or blocked status with clear justification. You do not write source code or run shell commands. If something is missing, you block closeout."

    def __init__(self, config=None, **kwargs):
        super().__init__("rex", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        template = (
            f"# Governance & Compliance Audit\n\n## Task: {title}\n\n"
            f"## Compliance Audit\n- Code & architecture reviewed\n- Policy gates validated\n- User sign-off required\n"
        )
        from workers.tools import ToolExecutor
        from backend.services.tool_permissions import check_tool_permission
        repo_path = task_context.get("repo_path", "")
        # THINKER role: Rex audits/inspects deliverables — read-only tools only,
        # never write_file or shell (role/tool enforcement).
        # Governor produces COMPLIANCE.md: docs-scoped write_file (documentation
        # paths only), never shell (role/tool enforcement).
        tool_executor = ToolExecutor(
            workspace_root=repo_path,
            permission_checker=lambda tn: check_tool_permission("rex", tn),
            allowed_tools=["explore", "read_file", "search", "write_file"],
            write_scope="docs",
        )
        content, meta, tool_calls = await _llm_with_tools(self,
            f"Governance audit: {title}\n{description}",
            _SPRINTER, 0.2, "governor", template, task_context=task_context, tool_executor=tool_executor)
        return _result_from_llm(content, meta, tool_calls=tool_calls)


class HermesWorker(BaseWorker):
    """System Dispatcher butler."""
    SYSTEM_PROMPT = "You are Hermes, the Dispatcher. You own the complete workflow from user request to delivery. Responsibilities: (1) Gather requirements via discovery/clarification with the user. (2) Produce docs/PRD.md from the collected brief—this is your output artifact delivered to the team. (3) Route/schedule tasks to specialist workers (pm, research, architect, designer, backend, frontend, qa, etc.)—never code yourself. (4) Track progress, aggregate results, and report back to the user with outcome summary. You NEVER write source code or edit project files—documentation only."

    def __init__(self, config=None, **kwargs):
        super().__init__("hermes", config, **kwargs)

    async def execute(self, task_context: dict) -> WorkerResult:
        return WorkerResult(success=True, output="Task dispatched by Hermes.")


# ── Worker Registry (AIC Skill Canonical) ──────────────

WORKER_REGISTRY: dict[str, type[BaseWorker]] = {
    # 16 Canonical Entities
    "hermes": HermesWorker,
    "rex": GovernorWorker,
    "pm": PMWorker,
    "research": ResearchWorker,
    "designer": DesignerWorker,
    "documentation": DocumentationWorker,
    "architect": ArchitectWorker,
    "backend": BackendWorker,
    "frontend": FrontendWorker,
    "qa": TestingWorker,
    "performance": PerformanceWorker,
    "database": DatabaseWorker,
    "nexus": DevOpsWorker,
    "flint": DeploymentWorker,
    "security": SecurityWorker,
    # Extensions & Aliases
    "coding": CodingWorker,
    "devops": DevOpsWorker,
    "deployment": DeploymentWorker,
    "debugger": TestingWorker,  # alias → Eve (QA + Bug Hunter)
    "planner": PMWorker,
    "testing": TestingWorker,
}


def get_worker(worker_type: str, config: dict | None = None) -> BaseWorker:
    """Get a worker instance by type."""
    cls = WORKER_REGISTRY.get(worker_type)
    if not cls:
        raise ValueError(f"Unknown worker type: {worker_type}")
    return cls(config)
