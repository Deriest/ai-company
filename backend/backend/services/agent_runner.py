"""Agent runner — executes workers with real tool calling (OpenCode-style).

This is the key innovation: workers actually READ files, WRITE code,
RUN tests, SEARCH codebases — not just chat.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional
from backend.services.tool_executor import WorkerToolExecutor, ToolResult, get_tools_for_worker, check_permission
from backend.services.context_builder import ContextBuilder, get_context_policy
from backend.services.context_overflow import estimate_tokens, handle_overflow
from backend.services.deliverable_collector import DeliverableCollector
from llm.provider import provider_manager, ModelTier

logger = logging.getLogger("aic.agent_runner")


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
    ) -> AsyncGenerator[dict, None]:
        """Run agent with tool execution loop, yielding events.
        
        When *db*, *provider_id* and *model_id* are provided the runner
        queries the real model context window and applies overflow
        handling (summarization / truncation) before each LLM call.
        """
        
        tools = get_tools_for_worker(worker_type)
        collector = DeliverableCollector()

        policy = get_context_policy(model_tier)

        # Build context using context builder with policy
        ctx, policy = await self.context_builder.build_context(
            worker_type=worker_type,
            task_description=prompt,
            conversation_history=conversation_history or [],
            system_prompt=system_prompt,
            model_tier=model_tier,
            db=db,
            provider_id=provider_id,
            model_id=model_id,
        )

        # Convert context to messages using policy limits
        messages, ctx_metadata = ctx.to_messages(policy=policy)
        messages.append({"role": "user", "content": prompt})
        
        tier_map = {"thinker": ModelTier.THINKER, "crafter": ModelTier.CRAFTER, "sprinter": ModelTier.SPRINTER}
        tier = tier_map.get(model_tier, ModelTier.CRAFTER)
        
        provider = provider_manager.get_active()
        if not provider:
            yield {"type": "error", "error": "No LLM provider configured"}
            return
        
        tool_executor_map = {
            "read_file": lambda a: self.executor.read_file(a.get("path", ""), a.get("offset", 0), a.get("limit", -1)),
            "write_file": lambda a: self.executor.write_file(a.get("path", ""), a.get("content", "")),
            "list_directory": lambda a: self.executor.list_directory(a.get("path", ".")),
            "search_files": lambda a: self.executor.search_files(a.get("pattern", ""), a.get("path", "."), a.get("file_pattern", "*")),
            "run_shell": lambda a: self.executor.run_shell(a.get("command", ""), a.get("timeout", 30)),
            "mcp_call": lambda a: self.executor.mcp_call(a.get("tool_name", ""), a.get("arguments", {})),
        }
        
        all_tool_results = []
        
        for iteration in range(max_iterations):
            # ── Overflow guard ──────────────────────────────────────
            # Check estimated tokens against the policy budget and
            # compress/truncate when necessary.
            if estimate_tokens(messages) > policy.max_tokens:
                yield {"type": "overflow_warning", "estimated": estimate_tokens(messages), "budget": policy.max_tokens}
                messages, overflow_strategy = await handle_overflow(messages, policy.max_tokens, provider)
                yield {"type": "overflow_resolved", "strategy": overflow_strategy, "message_count": len(messages)}

            # Call LLM with tools
            try:
                result = await provider.chat(
                    messages=messages,
                    tier=tier,
                    temperature=0.3,
                    max_tokens=policy.response_tokens,
                    tools=tools,
                )
            except Exception as e:
                yield {"type": "error", "error": f"LLM error: {str(e)}"}
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
