"""Agent tool definitions - OpenAI function calling format."""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to understand existing code before making changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"},
                    "offset": {"type": "integer", "description": "Line offset to start reading from", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines to read (-1 for all)", "default": -1},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"},
                    "content": {"type": "string", "description": "File content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": "."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text patterns in files (grep-like).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                    "file_pattern": {"type": "string", "description": "File glob pattern", "default": "*"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command. Use for running tests, building, git operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                },
                "required": ["command"],
            },
        },
    },
]


def get_tools_for_agent(agent_type: str) -> list:
    """Get tool definitions filtered by agent type."""
    if agent_type in ("frontend", "backend", "coding", "fullstack"):
        return AGENT_TOOLS
    elif agent_type in ("architect", "research", "pm"):
        return [t for t in AGENT_TOOLS if t["function"]["name"] in ("read_file", "list_directory", "search_files")]
    elif agent_type in ("qa", "testing"):
        return [t for t in AGENT_TOOLS if t["function"]["name"] != "write_file"]
    elif agent_type == "security":
        return [t for t in AGENT_TOOLS if t["function"]["name"] != "write_file"]
    else:
        return AGENT_TOOLS[:2]
