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
from typing import AsyncGenerator, Optional
from backend.services.tool_executor import WorkerToolExecutor, ToolResult, get_tools_for_worker, check_permission
from backend.services.context_builder import ContextBuilder, get_context_policy
from backend.services.context_overflow import estimate_tokens, handle_overflow
from backend.services.deliverable_collector import DeliverableCollector
from llm.provider import provider_manager, ModelTier, _worker_fallback_chain

logger = logging.getLogger("aic.agent_runner")

# Maximum allowed size for an image attachment (data_url string length).
IMAGE_MAX_BYTES = 10 * 1024 * 1024


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
    ) -> AsyncGenerator[dict, None]:
        """Run agent with tool execution loop, yielding events.
        
        When *db*, *provider_id* and *model_id* are provided the runner
        queries the real model context window and applies overflow
        handling (summarization / truncation) before each LLM call.
        """
        
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
            "run_shell": lambda a: self.executor.run_shell(a.get("command", ""), a.get("timeout", 30)),
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
                            if script_path and Path(script_path).exists():
                                def make_tool_fn(sp=script_path):
                                    # QA-E2E FIX: quote the script path — a
                                    # plugin path containing "'" previously
                                    # broke out of the shell command.
                                    return lambda a: self.executor.run_shell(f"bash {shlex.quote(sp)}", 60)
                                tool_executor_map[pname] = make_tool_fn()
                                tools.append({"function": {"name": pname, "description": ptool.get("description", pname), "parameters": {"type": "object", "properties": ptool.get("arguments", {}), "additionalProperties": False}}})
                    # Inject plugin agent instructions into the context.
                    for instr in pctx.get("agent_instructions", []):
                        pdef.setdefault("_agent_instructions", []).append(instr)
                    # Inject plugin MCP server definitions.
                    for mcp_srv in pctx.get("mcp_servers", []):
                        if isinstance(mcp_srv, dict) and mcp_srv.get("name"):
                            logger.info(f"Plugin MCP server: {mcp_srv['name']}")
                    # Include plugin skill instructions in the prompt context.
                    p_instructions = pctx.get("instructions", "")
                    if p_instructions:
                        pdef.setdefault("_skill_instructions", p_instructions)
            except Exception as e:
                logger.warning(f"Plugin runtime injection failed: {e}")
        
        all_tool_results = []
        
        for iteration in range(max_iterations):
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
                yield {"type": "error", "error": f"LLM error: {last_error}"}
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
            
            # If no tool calls, we're done
            if not tool_calls:
                yield {"type": "done", "iterations": iteration + 1, "tool_results": all_tool_results, "deliverables": collector.get_summary().to_dict()}
                return
            
            # Execute tool calls
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            
            for call in tool_calls:
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
                
                # Check permission
                if not check_permission(worker_type, fn_name):
                    tool_result = ToolResult(
                        tool=fn_name, success=False, output="",
                        error=f"Permission denied: {worker_type} cannot use {fn_name}"
                    )
                else:
                    # Execute tool
                    tool_fn = tool_executor_map.get(fn_name)
                    if tool_fn:
                        tool_result = await tool_fn(args)
                    else:
                        tool_result = ToolResult(tool=fn_name, success=False, output="", error=f"Unknown tool: {fn_name}")
                
                all_tool_results.append({
                    "tool": fn_name,
                    "success": tool_result.success,
                    "output": tool_result.output[:5000],
                    "error": tool_result.error,
                    "metadata": tool_result.metadata,
                })

                # Record deliverable
                collector.record_tool_result(
                    tool=fn_name,
                    success=tool_result.success,
                    output=tool_result.output[:5000],
                    error=tool_result.error or "",
                    args=args,
                )
                
                # Emit tool result
                yield {
                    "type": "tool_result",
                    "tool": fn_name,
                    "success": tool_result.success,
                    "output": tool_result.output[:5000],
                    "error": tool_result.error,
                    "metadata": tool_result.metadata,
                    "call_id": call_id,
                }
                
                # Add tool result to messages
                tool_content = tool_result.output[:5000] if tool_result.success else f"Error: {tool_result.error}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_content,
                })
        
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
