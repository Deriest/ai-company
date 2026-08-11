"""Test Runner Service — Real Test Execution for Python and Node.js projects.

Provides structured test execution with timeout enforcement, exit code tracking,
and deterministic test results suitable for verification engine consumption.
"""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TestResult:
    """Structured test result from test execution.

    Attributes:
        exit_code: Exit code from test runner (0 = success)
        stdout: Standard output from tests
        stderr: Standard error from tests
        duration: Total execution time in seconds
        language: Detected project language (python, javascript, typescript)
        framework: Detected test framework (pytest, jest, mocha, etc.)
        timestamp: ISO-formatted completion time
        files_tested: List of test files that were executed
        summary: Human-readable test summary
    """
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    language: str
    framework: str
    timestamp: str
    files_tested: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def create(
        cls,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration: float,
        language: str,
        framework: str,
        files_tested: list[str] | None = None,
        summary: str = "",
    ) -> "TestResult":
        """Create TestResult directly (avoids CompletedProcess type issues)."""
        return cls(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
            language=language,
            framework=framework,
            timestamp=datetime.now(timezone.utc).isoformat(),
            files_tested=files_tested or [],
            summary=summary,
        )


class TestRunnerService:
    """Runs tests for Python and Node.js projects with timeout enforcement."""

    DEFAULT_TIMEOUT = 30  # seconds
    PROJECT_ROOT: Path = field(default_factory=lambda: Path.cwd())

    def __init__(self, project_root: Path | None = None, timeout: int = 30):
        """Initialize test runner.

        Args:
            project_root: Root directory of the project to test. Defaults to CWD.
            timeout: Maximum test execution time in seconds. Default 30s.
        """
        self.project_root = Path(project_root) if project_root else self.PROJECT_ROOT
        self.timeout = timeout

    async def run_tests(self) -> TestResult:
        """Run tests for detected project type.

        Detects project type by examining project configuration files:
        - package.json → Node.js/TypeScript/JavaScript
        - pyproject.toml with pytest → Python
        - setup.py with pytest imports → Python
        - pytest.ini → Python

        Returns:
            TestResult with structured test outcomes
        """
        logger = self._get_logger()
        project_type = await self._detect_project_type()

        logger.info(f"Detected project type: {project_type}")

        if project_type == "python":
            return await self._run_python_tests()
        elif project_type in ("javascript", "typescript", "nodejs"):
            return await self._run_nodejs_tests(project_type)
        else:
            return TestResult.create(
                exit_code=-1,
                stdout="",
                stderr=f"No supported test configuration found. Detected: {project_type}",
                duration=0.0,
                language="unknown",
                framework="none",
                summary="Unsupported project type for testing",
            )

    async def _detect_project_type(self) -> str:
        """Detect project type from configuration files.

        Detection priority:
        1. pyproject.toml + pytest → python
        2. pytest.ini → python
        3. setup.py + pytest → python
        4. package.json → nodejs/javascript/typescript

        Returns:
            One of: "python", "javascript", "typescript", "nodejs", "unsupported"
        """
        logger = self._get_logger()
        
        # Check for Python configurations first
        pyproject_path = self.project_root / "pyproject.toml"
        pytest_ini_path = self.project_root / "pytest.ini"
        setup_py_path = self.project_root / "setup.py"

        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text(encoding="utf-8")
                if "pytest" in content.lower():
                    logger.info("Found pyproject.toml with pytest dependency")
                    return "python"
            except Exception as e:
                logger.debug(f"Error reading pyproject.toml: {e}")

        if pytest_ini_path.exists():
            logger.info("Found pytest.ini configuration")
            return "python"

        if setup_py_path.exists():
            try:
                content = setup_py_path.read_text(encoding="utf-8")
                if "pytest" in content.lower():
                    logger.info("Found setup.py with pytest reference")
                    return "python"
            except Exception as e:
                logger.debug(f"Error reading setup.py: {e}")

        # Check for Node.js configuration
        package_json_path = self.project_root / "package.json"
        if package_json_path.exists():
            try:
                content = package_json_path.read_text(encoding="utf-8")
                data = json.loads(content)
                
                scripts = data.get("scripts", {})
                has_test_script = any("test" in key.lower() for key in scripts.keys())
                
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                all_deps = {**deps, **dev_deps}
                
                has_testing_lib = any(
                    pkg in all_deps 
                    for pkg in ["jest", "mocha", "vitest", "jasmine", "ava"]
                )
                
                if has_test_script or has_testing_lib:
                    # Determine exact type
                    main = data.get("main", "")
                    type_field = data.get("type", "")
                    
                    if type_field == "module" or main.endswith(".ts") or ".d.ts" in str(data.get("files", [])):
                        logger.info("Detected TypeScript project")
                        return "typescript"
                    elif main.endswith(".js") or "node_modules" in str(all_deps.keys()):
                        if any(pkg in all_deps for pkg in ["typescript"]):
                            logger.info("Detected TypeScript project (has ts dep)")
                            return "typescript"
                        
                        logger.info("Detected JavaScript/Node.js project")
                        return "javascript"
                    
                    logger.info("Detected Node.js project")
                    return "nodejs"
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Error reading package.json: {e}")

        logger.warning("No supported test configuration detected")
        return "unsupported"

    async def _run_python_tests(self) -> TestResult:
        """Run Python tests using pytest.

        Preferred order:
        1. pytest --tb=short (standard pytest)
        2. python -m pytest --tb=short (via module)
        3. python -m pytest tests/ --tb=short (explicit path)

        Returns:
            TestResult with Python test outcomes
        """
        logger = self._get_logger()
        logger.info("Running Python tests with pytest")

        start_time = time.monotonic()
        
        # Try different pytest invocation methods
        commands = [
            ["pytest", "--tb=short", "-q"],
            ["python", "-m", "pytest", "--tb=short", "-q"],
            ["python", "-m", "pytest", "tests/", "--tb=short", "-q"],
        ]

        last_error = None
        for cmd in commands:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=self.timeout,
                    )
                    elapsed = time.monotonic() - start_time
                    
                    stdout_decoded = stdout.decode() if stdout else ""
                    stderr_decoded = stderr.decode() if stderr else ""
                    return_code = proc.returncode if proc.returncode is not None else -1
                    
                    return TestResult.create(
                        exit_code=return_code,
                        stdout=stdout_decoded,
                        stderr=stderr_decoded,
                        duration=elapsed,
                        language="python",
                        framework="pytest",
                    )

                except asyncio.TimeoutError:
                    proc.kill()
                    stdout, stderr = await proc.communicate()
                    elapsed = time.monotonic() - start_time
                    
                    return TestResult.create(
                        exit_code=-1,
                        stdout=stdout.decode() if stdout else "",
                        stderr=f"Test execution timed out after {self.timeout}s\n{stderr.decode() if stderr else ''}",
                        duration=elapsed,
                        language="python",
                        framework="pytest",
                        summary=f"Timed out after {self.timeout}s",
                    )

            except FileNotFoundError:
                logger.warning(f"Command not found: {' '.join(cmd[:2])}")
                last_error = f"{cmd[0]} not found"
                continue
            except Exception as e:
                logger.error(f"Pytest command failed: {e}")
                last_error = str(e)
                continue

        return TestResult.create(
            exit_code=-1,
            stdout="",
            stderr=f"Pytest not available. Tried: {commands}\nLast error: {last_error}",
            duration=time.monotonic() - start_time,
            language="python",
            framework="pytest",
            summary="Python testing not available",
        )

    async def _run_nodejs_tests(self, project_type: str) -> TestResult:
        """Run Node.js tests using npm/yarn/pnpm test.

        Attempts multiple package managers in order:
        1. pnpm test
        2. yarn test
        3. npm test

        Falls back to specific test commands from package.json scripts.

        Returns:
            TestResult with Node.js test outcomes
        """
        logger = self._get_logger()
        logger.info(f"Running {project_type} tests")

        start_time = time.monotonic()

        # Get test script from package.json
        test_command = await self._get_npm_test_script()

        # Try package managers
        package_managers = ["pnpm", "yarn", "npm"]

        last_error = None
        for pm in package_managers:
            try:
                # If we have a custom test script, use it
                if test_command and pm != "npm":
                    # For non-npm, prepend PM name
                    cmd = [pm, "run", test_command.replace("test:", "").replace("test", ""), "--"]
                else:
                    cmd = [pm, "test", "--"]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=self.timeout,
                    )
                    elapsed = time.monotonic() - start_time
                    
                    # Detect framework from output or package.json
                    framework = await self._detect_nodejs_framework()
                    
                    stdout_decoded = stdout.decode() if stdout else ""
                    stderr_decoded = stderr.decode() if stderr else ""
                    return_code = proc.returncode if proc.returncode is not None else -1
                    
                    return TestResult.create(
                        exit_code=return_code,
                        stdout=stdout_decoded,
                        stderr=stderr_decoded,
                        duration=elapsed,
                        language=project_type,
                        framework=framework,
                    )

                except asyncio.TimeoutError:
                    proc.kill()
                    stdout, stderr = await proc.communicate()
                    elapsed = time.monotonic() - start_time
                    
                    return TestResult.create(
                        exit_code=-1,
                        stdout=stdout.decode() if stdout else "",
                        stderr=f"Test execution timed out after {self.timeout}s\n{stderr.decode() if stderr else ''}",
                        duration=elapsed,
                        language=project_type,
                        framework=await self._detect_nodejs_framework(),
                        summary=f"Timed out after {self.timeout}s",
                    )

            except FileNotFoundError:
                logger.warning(f"Package manager not found: {pm}")
                last_error = f"{pm} not found"
                continue
            except Exception as e:
                logger.error(f"Package manager '{pm}' failed: {e}")
                last_error = str(e)
                continue

        return TestResult.create(
            exit_code=-1,
            stdout="",
            stderr=f"No package manager available. Tried: {package_managers}\nLast error: {last_error}",
            duration=time.monotonic() - start_time,
            language=project_type,
            framework="unknown",
            summary="Node.js testing not available",
        )

    async def _get_npm_test_script(self) -> str | None:
        """Extract test script name from package.json.

        Looks for scripts like: "test": "...", "test:unit": "...", etc.

        Returns:
            Script name like "test", or None if not found
        """
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return None

        try:
            content = package_json.read_text(encoding="utf-8")
            data = json.loads(content)
            scripts = data.get("scripts", {})

            # Look for test-related scripts
            for key in sorted(scripts.keys()):
                if key.lower() == "test":
                    return key
                if key.lower().startswith("test:"):
                    return key

        except (json.JSONDecodeError, IOError):
            pass

        return None

    async def _detect_nodejs_framework(self) -> str:
        """Detect Node.js testing framework from package.json."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return "unknown"

        try:
            content = package_json.read_text(encoding="utf-8")
            data = json.loads(content)
            
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            all_deps = {**deps, **dev_deps}

            if "vitest" in all_deps:
                return "vitest"
            elif "jest" in all_deps:
                return "jest"
            elif "mocha" in all_deps:
                return "mocha"
            elif "jasmine" in all_deps:
                return "jasmine"
            elif "ava" in all_deps:
                return "ava"

        except (json.JSONDecodeError, IOError):
            pass

        return "unknown"

    def _get_logger(self) -> Any:
        """Get logger instance."""
        try:
            from logging import getLogger
            return getLogger(__name__)
        except Exception:
            # Fallback: simple print-based logger
            class SimpleLogger:
                def info(self, msg, *args): print(f"[INFO] {msg % args if args else msg}")
                def warning(self, msg, *args): print(f"[WARNING] {msg % args if args else msg}")
                def error(self, msg, *args): print(f"[ERROR] {msg % args if args else msg}")
                def debug(self, msg, *args): print(f"[DEBUG] {msg % args if args else msg}")
            return SimpleLogger()
