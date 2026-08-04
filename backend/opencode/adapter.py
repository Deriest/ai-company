"""AIC Platform — OpenCode Adapter.

OpenCode is the default coding execution engine.
AIC Platform controls OpenCode. OpenCode does not control AIC Platform.

This adapter:
- Creates coding sessions
- Provides repository context
- Sends task instructions
- Monitors execution
- Collects changed files and tests
- Returns artifacts
"""
import asyncio
import json
import logging
import os
from typing import Optional

from workers.base import BaseWorker, WorkerResult
from backend.config import settings

logger = logging.getLogger("aic.opencode")


class OpenCodeAdapter(BaseWorker):
    """Worker adapter for OpenCode CLI."""

    def __init__(self, config: dict | str | None = None):
        super().__init__("coding", config if isinstance(config, dict) else {})
        cfg = config if isinstance(config, dict) else {}
        self.binary = cfg.get("binary", settings.OPENCODE_BIN)
        self.timeout = cfg.get("timeout", settings.OPENCODE_TIMEOUT)

    async def execute(self, task_context: dict) -> WorkerResult:
        """Execute a coding task via OpenCode."""
        repo_path = task_context.get("repo_path", ".")
        task_id = task_context.get("task_id", "unknown")
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        prompt = task_context.get("prompt", "")

        # Build the instruction
        instruction = prompt or self._build_prompt(title, description, task_context)

        # Write prompt to temp file for OpenCode
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, prefix=f"aic-{task_id}-"
        ) as f:
            f.write(instruction)
            prompt_file = f.name

        try:
            # Run OpenCode
            result = await self._run_opencode(repo_path, prompt_file, task_context)
            return result
        finally:
            # Cleanup
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

    async def _run_opencode(self, repo_path: str, prompt_file: str, task_context: dict | None = None) -> WorkerResult:
        """Execute OpenCode CLI."""
        cmd = [
            self.binary,
            "run",
            "--prompt", prompt_file,
            "--cwd", repo_path,
            "--non-interactive",
        ]

        logger.info(f"OpenCode exec: {' '.join(cmd)}")

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )

            output = stdout.decode(errors="replace")
            err_output = stderr.decode(errors="replace")

            if proc.returncode == 0:
                # Collect changed files
                changed_files = await self._collect_changes(repo_path)

                return WorkerResult(
                    success=True,
                    exit_code=0,
                    output=output,
                    artifact_path=None,
                )
            else:
                return WorkerResult(
                    success=False,
                    exit_code=proc.returncode,
                    output=output,
                    error=err_output or f"OpenCode exited with code {proc.returncode}",
                )

        except asyncio.TimeoutError:
            # FIX: kill the orphaned OpenCode subprocess so it does not keep running.
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            logger.error(f"OpenCode timed out after {self.timeout}s")
            return WorkerResult(
                success=False,
                exit_code=124,
                error=f"OpenCode timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            logger.info("OpenCode binary not found — executing direct LLM code generation fallback")
            from workers.base import BackendWorker
            fallback_worker = BackendWorker(self.config)
            return await fallback_worker.execute(task_context or {})

    async def _collect_changes(self, repo_path: str) -> list[str]:
        """Collect list of changed files via git diff."""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "--name-only", "HEAD",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return [line.strip() for line in stdout.decode().splitlines() if line.strip()]
        except asyncio.TimeoutError:
            # FIX: kill the orphaned git subprocess.
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return []
        except Exception:
            return []

    def _build_prompt(self, title: str, description: str, context: dict) -> str:
        """Build a coding prompt for OpenCode."""
        return (
            f"# Task: {title}\n\n"
            f"## Description\n{description}\n\n"
            f"## Context\n"
            f"- Task type: {context.get('type', 'feature')}\n"
            f"- Repository: {context.get('repo_path', '.')}\n\n"
            f"## Instructions\n"
            f"1. Analyze the codebase\n"
            f"2. Implement the requested changes\n"
            f"3. Write or update tests as needed\n"
            f"4. Ensure code follows existing conventions\n"
            f"5. Do not commit — leave changes staged\n"
        )

    async def check_available(self) -> bool:
        """Check if OpenCode CLI is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False
