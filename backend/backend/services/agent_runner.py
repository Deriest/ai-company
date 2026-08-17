"""Agent runner — executes workers with real tool calling (OpenCode-style).

This is the key innovation: workers actually READ files, WRITE code,
RUN tests, SEARCH codebases — not just chat.
"""
import asyncio
import json
import base64
import shlex
import subprocess
import tempfile
import zipfile
from pathlib import Path
import logging
from typing import AsyncGenerator
from backend.services.tool_executor import WorkerToolExecutor, ToolResult, get_tools_for_worker, check_permission
from backend.services.context_builder import ContextBuilder, get_context_policy
from backend.services.context_overflow import estimate_tokens, handle_overflow
from backend.services.deliverable_collector import DeliverableCollector
from llm.provider import provider_manager, ModelTier, _worker_fallback_chain

logger = logging.getLogger("aic.agent_runner")

# Maximum allowed size for an image attachment (data_url string length).
IMAGE_MAX_BYTES = 10 * 1024 * 1024

# Maximum tool-output length fed back to the LLM, and the ceiling for any
# shell timeout the model may request (prevents timeout: 999999).
TOOL_OUTPUT_LIMIT = 5000
MAX_SHELL_TIMEOUT = 120

# Global cap on concurrent agent runs across every entry point (/chat/execute,
# /agent/run, /agent/run-sync). Each run holds a DB session, an open LLM stream,
# and possibly subprocesses, so unbounded parallelism (N open chats → N runs) is
# a resource-exhaustion risk. Entry routes acquire this before running an agent;
# the non-agent chat paths never touch it.
AGENT_RUN_SEMAPHORE = asyncio.Semaphore(4)

# Round-6 FIX: while waiting on the semaphore above, routes emit a "queued"
# status event so the UI shows the run is waiting instead of hanging silently.
# After this many seconds stuck in the queue, they emit a clean "queue is full"
# error instead of waiting forever.
AGENT_RUN_QUEUE_TIMEOUT = 300


def _truncate_output(text: str, limit: int = TOOL_OUTPUT_LIMIT) -> str:
    """Truncate output with a marker so the agent knows how to page further."""
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…(truncated, {len(text)} chars — use offset/limit to page)"


def _format_tool_result(tool_result) -> str:
    """Format a tool result for LLM feedback, always including output + exit code + error.

    FIX: a failing command that writes diagnostics to stdout (with empty stderr)
    previously surfaced as "Error: None" — the agent saw no signal. Now the output
    is always included alongside the exit code and error.
    """
    output = (tool_result.output or "") if tool_result.output else ""
    error = (tool_result.error or "").strip() if tool_result.error else ""
    exit_code = (tool_result.metadata or {}).get("exit_code")
    if tool_result.success:
        return _truncate_output(output)
    parts = []
    if output:
        parts.append(output)
    if exit_code is not None:
        parts.append(f"[exit {exit_code}]")
    if error:
        parts.append(f"Error: {error}")
    return _truncate_output("\n".join(parts))


async def _get_mcp_tools_for_agent(db) -> list[dict]:
    """Fetch MCP tool schemas and convert to OpenAI function format.

    BUG-17 FIX: AgentRunner was not receiving MCP tool definitions, so the LLM
    could not call MCP tools (like memory create_entities, search_nodes).

    Returns list of tool definitions in OpenAI format:
    [{"type": "function", "function": {"name": "mcp_<toolName>", ...}}]
    """
    if db is None:
        return []

    try:
        from backend.services.mcp_service import mcp_service
        mcp_schemas = await mcp_service.get_all_mcp_tool_schemas(db)

        mcp_tools = []
        for schema in mcp_schemas:
            tool_name = schema.get("name", "")
            if not tool_name:
                continue

            # Convert to OpenAI function calling format with mcp_ prefix
            mcp_tools.append({
                "type": "function",
                "function": {
                    "name": f"mcp_{tool_name}",
                    "description": schema.get("description", f"MCP tool: {tool_name}"),
                    "parameters": schema.get("inputSchema", {"type": "object", "properties": {}}),
                }
            })

        if mcp_tools:
            logger.info(f"Injected {len(mcp_tools)} MCP tools into AgentRunner: {[t['function']['name'] for t in mcp_tools]}")
        return mcp_tools

    except Exception as e:
        logger.warning(f"Failed to fetch MCP tools for agent: {e}")
        return []


class AgentRunner:
    """Run an AI agent with real tool execution loop.
    
    Flow:
    1. Send prompt + tool definitions to LLM
    2. LLM responds with text + tool_calls
    3. Execute each tool call
    4. Feed results back to LLM
    5. Repeat until LLM gives final answer (no more tool calls)
    """
    
    def __init__(self, workspace_root: str = "."):
        self.executor = WorkerToolExecutor(workspace_root)
        self.context_builder = ContextBuilder(workspace_root)

    @staticmethod
    def _extract_attachment_text(attachment: dict) -> str:
        """Extract local document text so non-image attachments are readable."""
        mime = str(attachment.get("mime_type", "")).lower()
        name = str(attachment.get("name", "attachment"))
        raw_url = str(attachment.get("data_url", ""))
        if "," not in raw_url:
            return ""
        try:
            data = base64.b64decode(raw_url.split(",", 1)[1])
            if mime.startswith("text/") or Path(name).suffix.lower() in {".md", ".txt", ".csv", ".json", ".py", ".ts", ".tsx", ".js"}:
                return data.decode("utf-8", errors="replace")[:200_000]
            if mime == "application/pdf" or Path(name).suffix.lower() == ".pdf":
                with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                    f.write(data); f.flush()
                    result = subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True, timeout=30)
                    return result.stdout[:200_000] if result.returncode == 0 else ""
            if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or Path(name).suffix.lower() == ".docx":
                with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
                    xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
                import re
                return re.sub(r"<[^>]+>", " ", xml)[:200_000]
        except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError):
            return ""
        return ""
    
    async def run_agent(
        self,
        worker_type: str,
        prompt: str,
        system_prompt: str = "",
        model_tier: str = "crafter",
        max_iterations: int = 10,
        conversation_history: list = None,
        db=None,
        provider_id: str | None = None,
        model_id: str | None = None,
        attachments: list | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Run agent with tool execution loop, yielding events.
        
        When *db*, *provider_id* and *model_id* are provided the runner
        queries the real model context window and applies overflow
        handling (summarization / truncation) before each LLM call.

        *cancel_event* (optional) is a cooperative cancellation flag: when set,
        the loop stops at the next safe checkpoint (between tool rounds and
        before each provider.call) and yields a clean "cancelled" event instead
        of continuing to run in the background after the client disconnects.
        """
        def _is_cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def _cancelled_event(iteration: int) -> dict:
            return {"type": "cancelled", "iterations": iteration, "reason": "User cancelled"}
        
        # BUG-17 FIX: Get static tools + merge MCP tool schemas
        tools = get_tools_for_worker(worker_type)
        mcp_tools = await _get_mcp_tools_for_agent(db)
        if mcp_tools:
            tools = tools + mcp_tools
        collector = DeliverableCollector()

        # Resolve assigned plugins and collect adapted instructions before building context.
        assigned_plugins = []
        plugin_skills = []  # extra skill instructions from plugins
        if db:
            try:
                from backend.plugin_engine import resolve_plugins_for_worker
                from backend.services.plugin_adapter import build_plugin_context
                assigned_plugins = await resolve_plugins_for_worker(db, worker_type)
                for p in assigned_plugins:
                    ppath = p.get("package_path", "")
                    if p.get("is_required") and (not ppath or not Path(ppath).exists()):
                        yield {"type": "error", "error": f"Required plugin '{p['name']}' is missing. Install or disable it first."}
                        return
                    if ppath and Path(ppath).exists():
                        pctx = build_plugin_context(ppath, p.get("components", []))
                        p["_ctx"] = pctx
                        # Gather skill/agent instructions for context injection.
                        instr = pctx.get("instructions", "")
                        if instr:
                            plugin_skills.append(f"[Plugin: {p['name']}]\n{instr}")
                        for ai in pctx.get("agent_instructions", []):
                            if ai:
                                plugin_skills.append(f"[Plugin Agent: {p['name']}]\n{ai}")
            except Exception as e:
                logger.warning(f"Plugin resolution failed for worker '{worker_type}': {e}")

        policy = get_context_policy(model_tier)

        # FIX: inject durable project memories so the agent does not start from
        # zero every run (mirrors conversation/engine.py memory retrieval).
        if db:
            try:
                from backend.memory_engine import retrieve_project_memories
                memories = await retrieve_project_memories(db, query=prompt, limit=5)
                if memories:
                    memory_lines = []
                    for m in memories:
                        key = m.get("key", "")
                        val = m.get("value")
                        if isinstance(val, dict):
                            val = val.get("content", json.dumps(val, default=str))
                        memory_lines.append(f"- {key}: {val}")
                    memory_context = "\n\n## Relevant project memories\n" + "\n".join(memory_lines)
                    system_prompt = f"{system_prompt}{memory_context}"
                    logger.info(f"Injected {len(memories)} project memories for worker '{worker_type}'")
            except Exception as e:
                logger.debug(f"Memory retrieval failed: {e}")

        # Build context using context builder with policy and plugin skills
        ctx, policy = await self.context_builder.build_context(
            worker_type=worker_type,
            task_description=prompt,
            conversation_history=conversation_history or [],
            system_prompt=system_prompt,
            skills=plugin_skills or None,
            model_tier=model_tier,
            db=db,
            provider_id=provider_id,
            model_id=model_id,
        )

        # Convert context to messages using policy limits
        messages, ctx_metadata = ctx.to_messages(policy=policy)
        if ctx_metadata.get("truncated"):
            logger.warning(
                f"Context truncated: dropped {ctx_metadata['dropped_messages']} messages, "
                f"estimated {ctx_metadata['estimated_tokens']} tokens "
                f"(budget {ctx_metadata['max_tokens_budget']})"
            )
        if attachments:
            parts: list[dict] = [{"type": "text", "text": prompt}]
            for attachment in attachments:
                data_url = attachment.get("data_url", "")
                if attachment.get("mime_type", "").startswith("image/") and data_url:
                    if len(data_url) > IMAGE_MAX_BYTES:
                        logger.warning(f"Image attachment too large ({len(data_url)} bytes > {IMAGE_MAX_BYTES})")
                        yield {"type": "error", "error": "Image too large (max 10MB). Attach a smaller image."}
                        return
                    parts.append({"type": "image_url", "image_url": {"url": data_url}})
                else:
                    extracted = self._extract_attachment_text(attachment)
                    if extracted:
                        parts.append({"type": "text", "text": f"\n[Attached document: {attachment.get('name', 'file')}]\n{extracted}"})
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": "user", "content": prompt})
        
        tier_map = {"thinker": ModelTier.THINKER, "crafter": ModelTier.CRAFTER, "sprinter": ModelTier.SPRINTER, "vision": ModelTier.VISION}
        tier = tier_map.get(model_tier, ModelTier.CRAFTER)

        # Worker fallback chain — only within the thinker/crafter/sprinter group.
        # If the assigned model for this worker errors, retry with the next
        # worker's model in the chain. Never falls back to providers/models the
        # user did not assign.
        #   thinker  error -> crafter  -> sprinter
        #   crafter  error -> thinker  -> sprinter
        #   sprinter error -> crafter  -> thinker
        # planner/reviewer/manager are not in the 3-worker group — no cross-cover.
        tier_chain = _worker_fallback_chain(tier)
        
        # QA-2441 FIX: get_active() returns the FIRST registered provider,
        # which may have an empty api_key (e.g. VansRouter from env), causing
        # "Illegal header value b'Bearer '". Pick a provider with a usable key.
        provider = provider_manager.get_active_with_key()
        if not provider:
            yield {"type": "error", "error": "No LLM provider configured"}
            return
        if tier == ModelTier.VISION and not provider.config.get_model(ModelTier.VISION):
            yield {"type": "error", "error": "Vision model is not configured. Select a model that supports vision in the Vision tier."}
            return
        # QA-E2E FIX: also guard non-vision tiers — an empty model (e.g. a
        # provider with no provider_models/worker_runtime rows) would otherwise
        # produce a confusing 404/400 from the upstream API.
        if not provider.config.get_model(tier):
            yield {"type": "error", "error": f"Model is not configured for tier '{tier}'. Select a model in Settings > Providers."}
            return
        
        tool_executor_map = {
            "read_file": lambda a: self.executor.read_file(a.get("path", ""), a.get("offset", 0), a.get("limit", -1)),
            "write_file": lambda a: self.executor.write_file(a.get("path", ""), a.get("content", "")),
            "list_directory": lambda a: self.executor.list_directory(a.get("path", ".")),
            "search_files": lambda a: self.executor.search_files(a.get("pattern", ""), a.get("path", "."), a.get("file_pattern", "*")),
            # FIX: clamp the model-supplied timeout so a runaway `timeout: 999999`
            # cannot pin a subprocess forever, and always run shell commands in
            # the resolved workspace root (never the process cwd).
            "run_shell": lambda a: self.executor.run_shell(
                a.get("command", ""),
                min(int(a.get("timeout", 30) or 30), MAX_SHELL_TIMEOUT),
            ),
            "mcp_call": lambda a: self.executor.mcp_call(a.get("tool_name", ""), a.get("arguments", {})),
        }

        # BUG-17 FIX: Add dynamic routing for mcp_* prefixed tools
        # When LLM calls mcp_create_entities, route to mcp_call("create_entities", args)
        for mcp_tool_def in mcp_tools:
            mcp_fn_name = mcp_tool_def["function"]["name"]  # e.g., "mcp_create_entities"
            actual_tool_name = mcp_fn_name[4:]  # strip "mcp_" prefix → "create_entities"
            # Capture actual_tool_name in closure
            tool_executor_map[mcp_fn_name] = (
                lambda a, tn=actual_tool_name: self.executor.mcp_call(tn, a)
            )
        
        # Plugin runtime injection: adapted commands → tools, agents → instructions, hooks → permissions.
        plugin_tool_names: list[str] = []  # G3: plugin tools to auto-grant to this worker
        if db and assigned_plugins:
            try:
                from backend.services.plugin_adapter import build_plugin_context
                for pdef in assigned_plugins:
                    ppath = pdef.get("package_path", "")
                    if not ppath or not Path(ppath).exists():
                        continue
                    pctx = build_plugin_context(ppath, pdef.get("components", []))
                    # Inject plugin tools into the executor map.
                    for ptool in pctx.get("tools", []):
                        pname = ptool.get("name", "")
                        if pname and pname not in tool_executor_map:
                            script_path = ptool.get("script_path", "")
                            # G6 FIX: JSON command defs may store a relative
                            # script path; resolve against the package dir so
                            # exist() is true regardless of the process cwd.
                            if script_path and not Path(script_path).exists():
                                candidate = Path(ppath) / script_path
                                if candidate.exists():
                                    script_path = str(candidate)
                            if script_path and Path(script_path).exists():
                                def make_tool_fn(sp=script_path):
                                    # QA-E2E FIX: quote the script path — a
                                    # plugin path containing "'" previously
                                    # broke out of the shell command.
                                    return lambda a: self.executor.run_shell(f"bash {shlex.quote(sp)}", 60)
                                tool_executor_map[pname] = make_tool_fn()
                                plugin_tool_names.append(pname)
                                tools.append({"function": {"name": pname, "description": ptool.get("description", pname), "parameters": {"type": "object", "properties": ptool.get("arguments", {}), "additionalProperties": False}}})
                    # Inject plugin agent instructions into the context.
                    for instr in pctx.get("agent_instructions", []):
                        pdef.setdefault("_agent_instructions", []).append(instr)
                    # G2 FIX: register plugin-declared MCP servers in mcp_service
                    # (DB + pool) instead of only logging them. The pool's stdio
                    # allowlist still applies; non-allowlisted endpoints surface a
                    # clear warning instead of being silently ignored.
                    for mcp_srv in pctx.get("mcp_servers", []):
                        if isinstance(mcp_srv, dict) and mcp_srv.get("name"):
                            try:
                                from backend.services.mcp_service import mcp_service
                                if db is not None:
                                    status = await mcp_service.register_plugin_server(
                                        db, pdef.get("plugin_id", ""), mcp_srv
                                    )
                                    if status.get("status") != "connected":
                                        err = status.get("error") or "unknown error"
                                        logger.warning(f"Plugin MCP server '{mcp_srv['name']}' not connected: {err}")
                                        yield {"type": "warning", "message": f"Plugin MCP server '{mcp_srv['name']}' could not be connected: {err}"}
                                    else:
                                        logger.info(f"Plugin MCP server '{mcp_srv['name']}' connected (server_id={status.get('server_id')})")
                                else:
                                    logger.info(f"Plugin MCP server '{mcp_srv['name']}' registered (no db session)")
                            except Exception as mcp_err:
                                logger.warning(f"Plugin MCP server registration failed: {mcp_err}")
                    # Include plugin skill instructions in the prompt context.
                    p_instructions = pctx.get("instructions", "")
                    if p_instructions:
                        pdef.setdefault("_skill_instructions", p_instructions)
            except Exception as e:
                logger.warning(f"Plugin runtime injection failed: {e}")
        
        all_tool_results = []

        # FIX: stuck-loop detection — track identical (tool, args) signatures.
        call_signatures: dict[str, int] = {}
        loop_warned = False
        # FIX: self-check — ask the model to verify before finishing exactly once.
        verify_prompted = False

        for iteration in range(max_iterations):
            # ── Cooperative cancellation ─────────────────────────────
            # Check between tool rounds: if the client disconnected and the
            # caller set the cancel event, stop instead of running on.
            if _is_cancelled():
                yield _cancelled_event(iteration)
                return

            # ── Overflow guard ──────────────────────────────────────
            # Check estimated tokens against the policy budget and
            # compress/truncate when necessary.
            if estimate_tokens(messages) > policy.max_tokens:
                yield {"type": "overflow_warning", "estimated": estimate_tokens(messages), "budget": policy.max_tokens}
                messages, overflow_strategy = await handle_overflow(messages, policy.max_tokens, provider)
                yield {"type": "overflow_resolved", "strategy": overflow_strategy, "message_count": len(messages)}

            # Call LLM with tools — try the worker's tier first, then fall back
            # through the chain (thinker/crafter/sprinter cover each other on error).
            result = None
            last_error = None
            for attempt_tier in tier_chain:
                # FIX: cooperative cancellation — don't start a fresh LLM call
                # after the user has stopped the stream.
                if _is_cancelled():
                    yield _cancelled_event(iteration)
                    return
                try:
                    result = await provider.chat(
                        messages=messages,
                        tier=attempt_tier,
                        temperature=0.3,
                        max_tokens=policy.response_tokens,
                        tools=tools,
                    )
                    if attempt_tier != tier_chain[0]:
                        yield {"type": "fallback", "from": tier.value if hasattr(tier, 'value') else str(tier),
                               "to": attempt_tier.value if hasattr(attempt_tier, 'value') else str(attempt_tier),
                               "reason": str(last_error)[:200]}
                        logger.warning(
                            f"Worker '{worker_type}' fallback: {tier} -> {attempt_tier} after error: {last_error}"
                        )
                    break  # success — stop trying further tiers
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"LLM call failed for tier {attempt_tier} (worker {worker_type}): {e}"
                    )
                    continue  # try next tier in chain

            if result is None:
                # Round-6 FIX: the raw exception is already logged per-attempt
                # above; keep the client-facing error fixed and friendly.
                logger.error(
                    f"Agent execution failed for worker '{worker_type}': all LLM "
                    f"tiers in chain failed. Last error: {last_error}"
                )
                yield {"type": "error", "error": "Agent execution failed: LLM call failed. Check the provider configuration and try again."}
                return
            
            content = result.get("content", "")
            raw_msg = (result.get("raw") or {}).get("choices", [{}])[0].get("message", {})
            tool_calls = raw_msg.get("tool_calls", []) if isinstance(raw_msg, dict) else []
            
            # Clean thinking tags
            import re
            if content:
                for tag in ("thinking", "thought", "reason"):
                    content = re.sub(rf'<{tag}>.*?</{tag}>', '', content, flags=re.DOTALL).strip()
            
            # Emit content
            if content:
                yield {"type": "content", "content": content}
            
            # If no tool calls, we're done — unless we haven't asked for a final
            # self-check verification yet (FIX: verify step before finishing).
            if not tool_calls:
                if not verify_prompted:
                    verify_prompted = True
                    messages.append({
                        "role": "system",
                        "content": (
                            "Before finishing, verify your work: run any relevant tests or "
                            "syntax checks (e.g. `pytest`, `tsc --noEmit`, `python -m py_compile`) "
                            "using the available tools. If checks pass or you confirm the changes "
                            "are correct, provide your final answer."
                        ),
                    })
                    yield {"type": "status", "message": "Requesting self-check verification before final answer"}
                    continue
                yield {"type": "done", "iterations": iteration + 1, "tool_results": all_tool_results, "deliverables": collector.get_summary().to_dict()}
                return
            
            # Execute tool calls
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            
            for call in tool_calls:
                # FIX: cooperative cancellation — stop before executing the
                # next tool round when the user has stopped the stream.
                if _is_cancelled():
                    yield _cancelled_event(iteration)
                    return

                fn = call.get("function", {})
                fn_name = fn.get("name", "")
                fn_args_raw = fn.get("arguments", "{}")
                call_id = call.get("id", f"call_{iteration}_{fn_name}")
                
                try:
                    args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except json.JSONDecodeError:
                    args = {}
                
                # Emit tool start
                yield {"type": "tool_start", "tool": fn_name, "args": args, "call_id": call_id}
                
                # Check permission (G3: plugin-cmd_* tools are auto-granted for
                # workers the plugin is assigned to via plugin_tool_names).
                if not check_permission(worker_type, fn_name, allowed_plugin_tools=plugin_tool_names):
                    tool_result = ToolResult(
                        tool=fn_name, success=False, output="",
                        error=f"Permission denied: {worker_type} cannot use {fn_name}"
                    )
                else:
                    # Execute tool
                    tool_fn = tool_executor_map.get(fn_name)
                    if tool_fn:
                        # FIX: bound every tool call so a hanging tool (e.g. a
                        # shell command that backgrounds a process and holds the
                        # pipe open) can never stall the generator forever.
                        # run_shell already clamps to MAX_SHELL_TIMEOUT; this
                        # outer bound is a safety net (+5s) and cancels the tool
                        # coroutine on timeout (which triggers its own
                        # process-group kill).
                        try:
                            tool_result = await asyncio.wait_for(
                                tool_fn(args),
                                timeout=MAX_SHELL_TIMEOUT + 5,
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Tool '{fn_name}' hung longer than {MAX_SHELL_TIMEOUT + 5}s — aborting the call"
                            )
                            tool_result = ToolResult(
                                tool=fn_name, success=False, output="",
                                error=f"Tool '{fn_name}' timed out after {MAX_SHELL_TIMEOUT + 5}s (possible backgrounded process holding the pipe open)",
                            )
                    else:
                        tool_result = ToolResult(tool=fn_name, success=False, output="", error=f"Unknown tool: {fn_name}")
                
                all_tool_results.append({
                    "tool": fn_name,
                    "success": tool_result.success,
                    "output": _truncate_output(tool_result.output),
                    "error": tool_result.error,
                    "metadata": tool_result.metadata,
                })

                # Record deliverable
                collector.record_tool_result(
                    tool=fn_name,
                    success=tool_result.success,
                    output=_truncate_output(tool_result.output),
                    error=tool_result.error or "",
                    args=args,
                )
                
                # Emit tool result
                yield {
                    "type": "tool_result",
                    "tool": fn_name,
                    "success": tool_result.success,
                    "output": _truncate_output(tool_result.output),
                    "error": tool_result.error,
                    "metadata": tool_result.metadata,
                    "call_id": call_id,
                }
                
                # Add tool result to messages (always include output + exit code + error)
                tool_content = _format_tool_result(tool_result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_content,
                })

                # Stuck-loop detection (FIX): after 3 identical (tool, args)
                # repeats, inject a "stop and summarize" nudge once.
                try:
                    sig = f"{fn_name}:{json.dumps(args, sort_keys=True, default=str)}"
                except Exception:
                    sig = f"{fn_name}:unserializable"
                call_signatures[sig] = call_signatures.get(sig, 0) + 1
                if call_signatures[sig] >= 3 and not loop_warned:
                    loop_warned = True
                    messages.append({
                        "role": "system",
                        "content": (
                            "You appear to be looping: you have repeated the same tool call "
                            "3 times with identical arguments. Stop repeating the same action — "
                            "analyze the previous result, change your approach, and summarize "
                            "your findings."
                        ),
                    })
                    yield {"type": "warning", "message": "Detected repeated identical tool calls — prompting the agent to stop looping"}
        
        yield {"type": "done", "iterations": max_iterations, "note": "Max iterations reached", "tool_results": all_tool_results, "deliverables": collector.get_summary().to_dict()}


# Convenience function
async def run_worker_with_tools(
    worker_type: str,
    prompt: str,
    system_prompt: str = "",
    workspace_root: str = ".",
    model_tier: str = "crafter",
    db=None,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> dict:
    """Run a worker with tool execution and return final result."""
    runner = AgentRunner(workspace_root=workspace_root)
    final_content = ""
    tool_results = []
    
    async for event in runner.run_agent(
        worker_type,
        prompt,
        system_prompt,
        model_tier,
        db=db,
        provider_id=provider_id,
        model_id=model_id,
    ):
        if event["type"] == "content":
            final_content += event.get("content", "")
        elif event["type"] == "tool_result":
            tool_results.append(event)
        elif event["type"] == "error":
            return {"success": False, "error": event["error"], "content": final_content, "tool_results": tool_results}
        elif event["type"] == "done":
            return {"success": True, "content": final_content, "tool_results": tool_results, "iterations": event.get("iterations", 0)}
    
    return {"success": True, "content": final_content, "tool_results": tool_results}
