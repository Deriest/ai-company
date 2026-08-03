"""Plugin adapter framework — converts external plugin components to AIC-ADE worker system.

Adapter types:
- commands → worker tool definitions
- agents → worker instruction strings
- hooks → permission-guarded event callbacks
- mcp → MCP server registration
- skill/scripts → direct context injection
"""
import json
import os
import re
from pathlib import Path
from typing import Any


def _read_manifest(package_dir: str) -> dict:
    """Read the plugin manifest from a package directory."""
    p = Path(package_dir)
    for candidate in (p / ".claude-plugin" / "marketplace.json",
                      p / "plugin.json",
                      p / ".claude-plugin" / "plugin.json"):
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def adapt_commands_to_tools(package_dir: str) -> list[dict]:
    """Convert plugin commands/ directory into worker tool definitions."""
    commands_dir = Path(package_dir) / "commands"
    if not commands_dir.is_dir():
        return []
    tools = []
    for f in sorted(commands_dir.iterdir()):
        if f.suffix in (".sh", ".py", ".js", ".ts", ".mjs"):
            name = re.sub(r"[^a-z0-9_-]", "_", f.stem.lower())
            tools.append({
                "name": f"plugin_cmd_{name}",
                "description": f"Plugin command: {f.stem}",
                "plugin_source": package_dir,
                "script_path": str(f),
                "type": "script",
            })
    # Also check for JSON/YAML command definitions
    for f in commands_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, list):
                for cmd in data:
                    tools.append({
                        "name": f"plugin_{cmd.get('name', f.stem)}",
                        "description": cmd.get("description", ""),
                        "plugin_source": package_dir,
                        "script_path": cmd.get("script", ""),
                        "type": "json_command",
                        "arguments": cmd.get("arguments", {}),
                    })
        except (json.JSONDecodeError, OSError):
            pass
    return tools


def adapt_agents_to_instructions(package_dir: str) -> list[str]:
    """Convert plugin agents/ directory into worker instruction strings."""
    agents_dir = Path(package_dir) / "agents"
    if not agents_dir.is_dir():
        return []
    instructions = []
    for f in sorted(agents_dir.iterdir()):
        if f.suffix in (".md", ".txt"):
            instructions.append(f.read_text(encoding="utf-8", errors="replace").strip()[:10000])
        elif f.suffix == ".json":
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    instructions.append(data.get("instructions", data.get("prompt", "")))
            except (json.JSONDecodeError, OSError):
                pass
    return instructions


def adapt_hooks_to_permissions(package_dir: str) -> list[dict]:
    """Convert plugin hooks/ directory into permission-checked event handlers."""
    hooks_dir = Path(package_dir) / "hooks"
    if not hooks_dir.is_dir():
        return []
    hooks = []
    for f in sorted(hooks_dir.iterdir()):
        if f.suffix in (".sh", ".py", ".js"):
            hooks.append({
                "name": f.stem,
                "script_path": str(f),
                "plugin_source": package_dir,
                "required_permissions": ["execute_script"],
            })
    return hooks


def adapt_mcp_servers(package_dir: str) -> list[dict]:
    """Read MCP server definitions from plugin manifest or mcp/ directory."""
    mcp_dir = Path(package_dir) / "mcp"
    servers = []
    if mcp_dir.is_dir():
        for f in mcp_dir.glob("*.json"):
            try:
                servers.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
    manifest = _read_manifest(package_dir)
    for entry in manifest.get("mcp", []):
        if isinstance(entry, dict):
            servers.append(entry)
    return servers


def adapt_skill_instructions(package_dir: str) -> str:
    """Extract instructions from SKILL.md or README.md in the package."""
    p = Path(package_dir)
    for name in ("SKILL.md", "skill.md", "README.md"):
        skill_file = p / name
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8", errors="replace")[:50000]
    return ""


def build_plugin_context(package_dir: str, components: list[str]) -> dict[str, Any]:
    """Build complete plugin context for worker injection."""
    context = {
        "package_path": package_dir,
        "components": components,
        "instructions": "",
        "tools": [],
        "agent_instructions": [],
        "hooks": [],
        "mcp_servers": [],
    }

    if "skill" in components:
        context["instructions"] = adapt_skill_instructions(package_dir)

    if "commands" in components:
        context["tools"] = adapt_commands_to_tools(package_dir)

    if "agents" in components:
        context["agent_instructions"] = adapt_agents_to_instructions(package_dir)

    if "hooks" in components:
        context["hooks"] = adapt_hooks_to_permissions(package_dir)

    if "mcp" in components:
        context["mcp_servers"] = adapt_mcp_servers(package_dir)

    if "scripts" in components:
        scripts_dir = Path(package_dir) / "scripts"
        if scripts_dir.is_dir():
            context["script_paths"] = [str(f) for f in sorted(scripts_dir.iterdir()) if f.suffix in (".sh", ".py", ".js")]

    return context