"""Tool-Aware Chat Service — OpenCode-style tool execution during chat.

When the LLM response contains tool-use markers, this service:
1. Parses the tool calls
2. Executes them via ToolExecutor
3. Emits structured events (tool_start, tool_result, file_diff, shell_output)
4. Feeds results back to the LLM for continuation
5. Streams the final response with all tool events interleaved

Events emitted via SSE:
  {"type": "chunk", "content": "..."}         — text chunk
  {"type": "tool_start", "tool_call": {...}}  — tool execution begins
  {"type": "tool_result", "tool_call": {...}} — tool execution ends
  {"type": "file_diff", "path": "...", ...}   — file was modified
  {"type": "shell_output", "command": "...", "chunk": "..."}  — shell streaming
  {"type": "todo_update", "items": [...]}     — todo list updated
  {"type": "files_modified", "paths": [...]}  — summary of changed files
  {"type": "done", "intent": "...", "metadata": {...}}
  {"type": "error", "error": "..."}
"""
import json
import re
import logging
import time
from typing import AsyncGenerator

from llm.provider import provider_manager, ModelTier
from workers.tools import ToolExecutor

logger = logging.getLogger("aic.tool_chat")

# Default chat tool permissions: only read-only tools are enabled for the
# generic chat path. write_file / shell / mcp_call are denied unless a
# permission checker is explicitly supplied (worker-scoped chat).
CHAT_DEFAULT_ALLOWED_TOOLS = frozenset({"read_file", "explore", "search"})


def _chat_permission_checker(worker_type: str | None = None):
    """Build a real permission checker for the chat tool path.

    S1 FIX: ``worker_type`` is client-supplied and UNTRUSTED. Previously a
    coder role (backend/frontend/qa/debugger/coding/devops/deployment) made the
    chat tool path shell-capable via ``check_permission``. The chat tool path
    now ALWAYS uses the safe read-only default allowlist regardless of the
    client-supplied ``worker_role`` — shell/write_file/mcp_call stay denied.
    """
    def _default_check(tool_name: str) -> bool:
        return tool_name in CHAT_DEFAULT_ALLOWED_TOOLS
    return _default_check

# ── Tool-use prompt injection ────────────────────────────

TOOL_SYSTEM_ADDENDUM = """

You have access to the following tools. When you need to use a tool, output it in this EXACT format on its own line:

[TOOL:type:args_json]

Where:
- type is one of: read_file, write_file, shell, explore, search
- args_json is a JSON object with the tool arguments

Examples:
[TOOL:read_file:{"path": "src/main.py"}]
[TOOL:write_file:{"path": "src/utils.py", "content": "def hello():\\n    return 'world'"}]
[TOOL:shell:{"command": "npm test", "timeout": 30}]
[TOOL:explore:{"path": "src", "max_depth": 2}]
[TOOL:search:{"pattern": "TODO|FIXME", "path": "."}]

After each tool call, you will receive the result. You can make multiple tool calls.
When you are done, provide your final response as normal text.

IMPORTANT: Always read files before modifying them. Always show what you're doing.
"""


def _build_mcp_tool_addendum(mcp_tools: list[dict]) -> str:
    """Build additional tool instructions for MCP-registered tools."""
    if not mcp_tools:
        return ""

    lines = ["\nAdditionally, you have access to these MCP tools:\n"]
    for t in mcp_tools:
        name = t.get("name", "")
        desc = t.get("description", "")
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        param_names = list(props.keys())
        lines.append(f"- [TOOL:mcp_call:{json.dumps({'tool_name': name, 'arguments': {p: '...' for p in param_names}})}]  — {desc}")

    lines.append("\nFor MCP tools, use: [TOOL:mcp_call:{\"tool_name\": \"<name>\", \"arguments\": {...}}]")
    return "\n".join(lines)

# Pattern to detect tool calls in LLM output
TOOL_PATTERN = re.compile(r'\[TOOL:(\w+):({[^]]+})\]')
TOOL_XML_PATTERN = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)
TOOL_JSON_PATTERN = re.compile(r'\{"tool"\s*:\s*"(\w+)"\s*,\s*"args"\s*:\s*(\{.*?\})\}', re.DOTALL)


def _parse_tool_calls(content: str) -> list[tuple[str, dict]]:
    """Parse tool calls from LLM output in multiple formats.

    Supported formats:
    - [TOOL:type:{json}]        (bracket format)
    - <tool_call>{json}</tool_call>  (XML-like format)
    - {"tool": "type", "args": {...}} (JSON format)

    Returns list of (tool_type, args_dict) tuples.
    """
    results = []

    # Format 1: [TOOL:type:{json}]
    for tool_type, args_str in TOOL_PATTERN.findall(content):
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        results.append((tool_type, args))

    # Format 2: <tool_call>...</tool_call>
    for match in TOOL_XML_PATTERN.finditer(content):
        xml_body = match.group(1).strip()
        try:
            parsed = json.loads(xml_body)
            tool_type = parsed.get("name") or parsed.get("tool") or parsed.get("type", "")
            tool_args = parsed.get("args") or parsed.get("arguments") or parsed.get("parameters") or {}
            if tool_type:
                results.append((tool_type, tool_args))
        except json.JSONDecodeError:
            pass

    # Format 3: {"tool": "type", "args": {...}}
    for tool_type, args_str in TOOL_JSON_PATTERN.findall(content):
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        results.append((tool_type, args))

    return results


class ToolAwareChatService:
    """Chat service that detects and executes tool calls from LLM responses."""

    def __init__(self, workspace_root: str = "", worker_type: str | None = None, permission_checker=None):
        self.workspace_root = workspace_root
        self._worker_type = worker_type
        self._permission_checker = permission_checker

    async def stream_with_tools(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        tier=None,
        worker_type: str | None = None,
        permission_checker=None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response with tool execution.

        Yields SSE-formatted strings.
        """
        # QA-2442 FIX: get_active() returns the FIRST registered provider,
        # which may have an empty api_key (e.g. VansRouter from env), causing
        # "Illegal header value b'Bearer '". Pick a provider with a usable key.
        provider = provider_manager.get_active_with_key()
        if not provider:
            # Fallback: try to load from .env
            from llm.provider import init_provider_from_env
            config = init_provider_from_env()
            if config:
                provider_manager.register(config)
                provider = provider_manager.get_active_with_key()
        if not provider:
            # Fallback: try DB provider
            try:
                from backend.database.session import AsyncSessionLocal
                from backend.models.schema import Provider
                from backend.services.crypto import decrypt as decrypt_api_key
                from sqlalchemy.future import select
                async with AsyncSessionLocal() as db:
                    res = await db.execute(select(Provider).where(Provider.enabled == True).limit(1))
                    p = res.scalars().first()
                    if p and p.enabled:
                        from llm.provider import ProviderConfig
                        config = ProviderConfig(
                            name=p.name,
                            base_url=p.base_url,
                            api_key=decrypt_api_key(p.api_key),
                        )
                        provider_manager.register(config)
                        provider = provider_manager.get_active_with_key()
            except Exception:
                pass
        if not provider:
            yield f"data: {json.dumps({'type': 'error', 'error': 'No AI provider configured. Please add a provider in Settings > Providers.'})}\n\n"
            return

        # Build messages with tool addendum + MCP tools
        sys_msg = (system_prompt or "") + TOOL_SYSTEM_ADDENDUM

        # Inject MCP tools if available
        try:
            from backend.database.session import AsyncSessionLocal
            from backend.services.mcp_service import mcp_service
            async with AsyncSessionLocal() as mcp_db:
                mcp_tools = await mcp_service.get_all_mcp_tool_schemas(mcp_db)
                if mcp_tools:
                    sys_msg += _build_mcp_tool_addendum(mcp_tools)
        except Exception:
            pass  # MCP tools optional

        llm_messages = [{"role": "system", "content": sys_msg}]
        llm_messages.extend(messages)

        # Create tool executor with streaming callback
        tool_events_emitted = []

        async def on_tool_event(event: dict):
            """Collect events to emit after tool execution."""
            tool_events_emitted.append(event)

        # QA-E2E FIX: previously the ToolExecutor was built with NO permission
        # checker, so LLM-controlled shell/write_file calls ran ungated in the
        # /chat/stream tool path. Pass a real permission checker now.
        executor = ToolExecutor(
            workspace_root=self.workspace_root,
            on_event=on_tool_event,
            permission_checker=permission_checker or self._permission_checker
            or _chat_permission_checker(worker_type or self._worker_type),
        )

        # Track modified files across the conversation
        all_modified_files = []
        all_todos = []
        max_tool_rounds = 10  # Prevent infinite tool loops

        for round_num in range(max_tool_rounds):
            # Call LLM
            try:
                result = await provider.chat(
                    messages=llm_messages,
                    tier=tier or ModelTier.CRAFTER,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    purpose="tool_chat",
                )
                content = (result.get("content") or "").strip()
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                return

            # Clean thinking tags
            for tag in ("thinking", "thought", "reason"):
                content = re.sub(rf'<{tag}>.*?</{tag}>', '', content, flags=re.DOTALL).strip()

            # Find tool calls
            tool_calls = _parse_tool_calls(content)

            if not tool_calls:
                # No tool calls — stream the final response
                # Clean any partial tool markers
                clean_content = TOOL_PATTERN.sub('', content)
                clean_content = TOOL_XML_PATTERN.sub('', clean_content)
                clean_content = TOOL_JSON_PATTERN.sub('', clean_content)
                clean_content = clean_content.strip()
                if clean_content:
                    # Stream in chunks
                    chunk_size = 20
                    for i in range(0, len(clean_content), chunk_size):
                        chunk = clean_content[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                break

            # Stream the text before the first tool call
            first_tool_pos = len(content)
            for marker in ['[TOOL:', '<tool_call>', '{"tool"']:
                pos = content.find(marker)
                if 0 <= pos < first_tool_pos:
                    first_tool_pos = pos
            if first_tool_pos > 0:
                prefix = content[:first_tool_pos].strip()
                if prefix:
                    chunk_size = 20
                    for i in range(0, len(prefix), chunk_size):
                        chunk = prefix[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            # Execute each tool call
            tool_results = []
            for tool_type, args in tool_calls:

                # Emit tool_start
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_type, 'args': args})}\n\n"

                # Execute tool
                if tool_type == "read_file":
                    tc = await executor.read_file(args.get("path", ""), args.get("offset", 0), args.get("limit", 2000))
                elif tool_type == "write_file":
                    tc = await executor.write_file(args.get("path", ""), args.get("content", ""))
                elif tool_type == "shell":
                    tc = await executor.run_shell(args.get("command", ""), max(1, min(600, int(args.get("timeout", 60) or 60))))
                elif tool_type == "explore":
                    tc = await executor.explore(args.get("path", "."), args.get("max_depth", 3))
                elif tool_type == "search":
                    tc = await executor.search(args.get("pattern", ""), args.get("path", "."))
                elif tool_type == "mcp_call":
                    # MCP tool execution via protocol client
                    from workers.tools import ToolCall
                    from datetime import datetime as _dt
                    mcp_tool_name = args.get("tool_name", "")
                    mcp_args = args.get("arguments", {})
                    tc = ToolCall(
                        id=executor._next_id(),
                        type="mcp_call",
                        label=f"MCP: {mcp_tool_name}",
                        status="running",
                        args=args,
                        timestamp=_dt.now().isoformat(),
                    )
                    await executor._emit("tool_start", {"tool_call": tc.to_dict()})
                    _start = time.monotonic()
                    try:
                        from backend.services.mcp_client import mcp_pool
                        mcp_result = await mcp_pool.call_tool(mcp_tool_name, mcp_args)
                        content_parts = mcp_result.get("content", [])
                        text_output = "\n".join(
                            p.get("text", "") for p in content_parts if p.get("type") == "text"
                        ) or json.dumps(mcp_result, indent=2)
                        tc.output = text_output[:10000]
                        tc.result = {"mcp_tool": mcp_tool_name, "content": mcp_result}
                        tc.status = "completed"
                    except Exception as mcp_err:
                        tc.status = "error"
                        tc.error = str(mcp_err)
                        tc.output = str(mcp_err)
                    tc.duration_ms = int((time.monotonic() - _start) * 1000)
                    executor.tool_calls.append(tc)
                    await executor._emit("tool_result", {"tool_call": tc.to_dict()})
                else:
                    tc = None

                if tc:
                    tool_results.append(f"Tool {tool_type} result:\n{tc.output[:3000]}")
                    # Emit tool_result
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_call': tc.to_dict()})}\n\n"

                    # Emit file_diffs
                    for diff in executor.file_diffs:
                        if diff not in [d for d in all_modified_files]:
                            yield f"data: {json.dumps({'type': 'file_diff', **diff.to_dict()})}\n\n"
                            all_modified_files.append(diff)

                    # Emit shell output events
                    for evt in tool_events_emitted:
                        if evt.get("type") == "shell_output":
                            yield f"data: {json.dumps(evt)}\n\n"
                    tool_events_emitted.clear()
                else:
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_type, 'error': f'Unknown tool: {tool_type}'})}\n\n"

            # Feed tool results back to LLM for next round
            tool_result_msg = "\n\n".join(tool_results)
            llm_messages.append({"role": "assistant", "content": content})
            llm_messages.append({"role": "user", "content": f"Tool results:\n{tool_result_msg}\n\nContinue with your task or provide your final response."})

        # Emit files_modified summary
        if all_modified_files:
            paths = [d.path for d in all_modified_files]
            yield f"data: {json.dumps({'type': 'files_modified', 'paths': paths})}\n\n"

        # Emit todos if any
        if executor.todos:
            yield f"data: {json.dumps({'type': 'todo_update', 'items': [t.to_dict() for t in executor.todos]})}\n\n"

        # Done
        yield f"data: {json.dumps({'type': 'done', 'metadata': executor.get_summary()})}\n\n"


# Module-level instance
tool_chat_service = ToolAwareChatService()
