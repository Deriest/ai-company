import os
import glob
import time
from pathlib import Path
from typing import Dict, Any, List

from backend.services.path_utils import resolve_workspace_path

class ToolDispatcher:
    def __init__(self, workspace_dir: str | None = None):
        # F10 FIX: do not default to a fixed world-writable /tmp path — a
        # pre-existing symlink there could redirect writes. Derive the root
        # from settings (DATA_DIR / AIC_DATA_DIR) like every other service.
        if workspace_dir is None:
            try:
                from backend.config import settings
                workspace_dir = str(settings.WORKSPACE_DIR)
            except Exception:
                workspace_dir = str(Path(__file__).resolve().parent.parent / "data" / "workspace")
        self.workspace_dir = workspace_dir
        os.makedirs(self.workspace_dir, exist_ok=True)

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            if tool_name == "read_file":
                res = self._read_file(arguments.get("path", ""))
            elif tool_name == "write_file":
                res = self._write_file(arguments.get("path", ""), arguments.get("content", ""))
            elif tool_name == "search_workspace":
                res = self._search_workspace(arguments.get("query", ""))
            elif tool_name == "list_directory":
                res = self._list_directory(arguments.get("path", "."))
            elif tool_name == "current_time":
                res = {"current_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            exec_time = int((time.time() - start_time) * 1000)
            return {"result": res, "error": None, "execution_time_ms": exec_time}
        except Exception as e:
            exec_time = int((time.time() - start_time) * 1000)
            return {"result": None, "error": str(e), "execution_time_ms": exec_time}

    def _read_file(self, path: str) -> Dict[str, Any]:
        full_path = resolve_workspace_path(self.workspace_dir, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return {"content": f.read()}

    def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        full_path = resolve_workspace_path(self.workspace_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "ok", "bytes_written": len(content)}

    def _list_directory(self, path: str) -> Dict[str, Any]:
        full_path = resolve_workspace_path(self.workspace_dir, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Directory not found: {path}")
        entries = []
        for item in os.listdir(full_path):
            p = os.path.join(full_path, item)
            entries.append({
                "name": item,
                "is_dir": os.path.isdir(p),
                "size": os.path.getsize(p) if os.path.isfile(p) else 0
            })
        return {"entries": entries}

    def _search_workspace(self, query: str) -> Dict[str, Any]:
        matches = []
        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                p = os.path.join(root, file)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        if query.lower() in f.read().lower():
                            rel = os.path.relpath(p, self.workspace_dir)
                            matches.append(rel)
                except Exception:
                    pass
        return {"matches": matches}

tool_dispatcher = ToolDispatcher()
