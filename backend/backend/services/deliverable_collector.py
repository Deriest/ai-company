"""Collect and package deliverables from agent execution."""
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from backend.services.content_utils import truncate_content


@dataclass
class DeliverableFile:
    path: str
    content: str
    action: str  # created, modified, read
    size: int = 0


@dataclass
class DeliverableSummary:
    files: list = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    test_output: str = ""
    shell_commands: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def to_dict(self):
        return {
            "files": [
                {
                    "path": f.path,
                    "action": f.action,
                    "size": f.size,
                    "preview": truncate_content(f.content, 500),
                }
                for f in self.files
            ],
            "tests": {
                "passed": self.tests_passed,
                "failed": self.tests_failed,
                "output": self.test_output[:2000],
            },
            "shell_commands": self.shell_commands,
            "errors": self.errors,
        }


class DeliverableCollector:
    """Collect deliverables from tool execution results."""

    def __init__(self):
        self.files: list[DeliverableFile] = []
        self.shell_results: list[dict] = []
        self.errors: list[dict] = []
        self.tests_passed: int = 0
        self.tests_failed: int = 0

    def record_tool_result(
        self, tool: str, success: bool, output: str, error: str, args: dict
    ):
        """Record a tool execution result as a deliverable."""
        if tool == "write_file" and success:
            self.files.append(
                DeliverableFile(
                    path=args.get("path", ""),
                    content=args.get("content", ""),
                    action="created",
                    size=len(args.get("content", "")),
                )
            )
        elif tool == "read_file" and success:
            self.files.append(
                DeliverableFile(
                    path=args.get("path", ""),
                    content=output[:2000],
                    action="read",
                    size=len(output),
                )
            )
        elif tool == "run_shell":
            self.shell_results.append(
                {
                    "command": args.get("command", ""),
                    "success": success,
                    "output": output[:1000] if success else error[:2000],
                    "status": "failed" if not success else "ok",
                }
            )
            # M2 (cycle-12) + L2 (cycle-14): bound list AND track failed runs
            # loop cannot grow the summary unboundedly (keep the most recent).
            if len(self.shell_results) > 200:
                self.shell_results = self.shell_results[-200:]
            # Check for test results
            if "test" in args.get("command", "").lower() and success:
                if "passed" in output:
                    match = re.search(r"(\d+) passed", output)
                    if match:
                        self.tests_passed = int(match.group(1))
                if "failed" in output:
                    match = re.search(r"(\d+) failed", output)
                    if match:
                        self.tests_failed = int(match.group(1))

        if error:
            self.errors.append({"tool": tool, "error": error[:200]})

    def get_summary(self) -> DeliverableSummary:
        """Get the deliverable summary."""
        return DeliverableSummary(
            files=self.files,
            tests_passed=self.tests_passed,
            tests_failed=self.tests_failed,
            test_output="\n".join(
                r["output"]
                for r in self.shell_results
                if "test" in r.get("command", "").lower()
            ),
            shell_commands=[r["command"] for r in self.shell_results],
            errors=self.errors,
        )
