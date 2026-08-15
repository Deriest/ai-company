"""AIC Platform — Shell command security patterns.

Shared denylist for shell commands with defense-in-depth protections.
This is NOT a substitute for sandboxing — denylist is ADVISORY ONLY; production MUST sandbox — only blocks clearly catastrophic patterns.

CRITICAL: This module consolidates previously duplicated denylists from tool_executor.py
and workers/tools.py into a single source of truth.
"""
import os
import re
import signal
import unicodedata
from urllib.parse import unquote

# ── Shell command safety patterns ──────────────────────
# Block dangerous patterns at WORD BOUNDARIES without trailing anchors that allow
# paths like /etc, /usr, /var to escape detection. Also blocks obfuscation and
# common attack vectors like curl|sh, wget|sh, pip install --trusted-host, etc.

_DANGEROUS_COMMANDS = [
    # ===== Destructive file removal =====
    r'\brm\s+-rf\s+/+',                     # rm -rf / (must have at least one slash)
    r'\brm\s+-rf\s+~\s*$',                  # rm -rf ~ (home directory)
    r'\brm\s+-rf\s+\$HOME\s*$',             # rm -rf $HOME

    # ===== Filesystem operations =====
    r'\bmkfs\b',                            # mkfs (format filesystem)
    r'\bdd\s+(?:if=\s*.+?|of=\s*.+?)?',     # dd (raw disk access)
    r'>\s*/dev/sd',                         # write to raw block device

    # ===== Code execution === 禁止 =====
    r'\b(eval|exec|system)\b',              # direct code execution

    # ===== Obfuscation attacks =====
    r"e['\"']?val",                         # e'val', eval obfuscation
    r"e['\"]?\x56\x61\x6c",                 # eval hex encoded
    r"`[^`]+`|\$\([^)]+\)",                 # backtick or $() command substitution

    # ===== Dangerous permission changes =====
    r'\bchmod\s+-R\s+777',                  # chmod -R 777 (any path)

    # ===== Fork bomb =====
    r':\(\)\s*\{[^}]*\};:',                 # fork bomb pattern

    # ===== Network exfiltration/download execute =====
    r'\bcurl\s+.*\|\s*(?:ba)?sh\b',         # curl ... | sh/bash
    r'\bwget\s+.*\|\s*(?:ba)?sh\b',         # wget ... | sh/bash
    r'\bpip\s+(?:install|uninstall).*--trusted-host',  # bypass SSL verification
    r'\bcurl\s+.*\|\s*sudo\s+(?:ba)?sh\b', # curl ... | sudo sh/bash
    r'\bwget\s+.*\|\s*sudo\s+(?:ba)?sh\b', # wget ... | sudo sh/bash

    # ===== Code execution via interpreters (-c / -e flags) =====
    r'\bbash\s+.*-c\b',                       # bash -c
    r'\bsh\s+.*-c\b',                         # sh -c
    r'\bperl\s+.*-e\b',                       # perl -e
    r'\bnode\s+.*-e\b',                       # node -e
    r'\bruby\s+.*-e\b',                       # ruby -e
    r'\bphp\s+.*-r\b',                        # php -r

    # ===== Wildcard / current-dir wipe =====
    r'\brm\s+-rf\s+\*',                      # rm -rf * (workspace wipe)
    r'\brm\s+-rf\s+\.\s',                    # rm -rf . (current dir)
    r'\brm\s+-rf\s+\./',                     # rm -rf ./
    r'\brm\s+-rf\s+\$PWD',                   # rm -rf $PWD

    # ===== Source / import bypass =====
    r'\bsource\s+',                            # source evil.sh
    r'\b\.\s+\./',                            # . ./evil.sh

    # ===== Sudo escalation =====
    r'\bsudo\s+.*\brm\b',                    # sudo rm
    r'\bsudo\s+.*\bmkfs\b',                  # sudo mkfs
    r'\bsudo\s+.*\bdd\b',                    # sudo dd

    # ===== Additional fork bomb variants =====
    r':\(\)',                                  # any :() fork bomb start
]

_DANGEROUS_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_COMMANDS]


def _normalize_command_for_check(command: str) -> str:
    """Normalize command to catch homoglyph attacks and decode URL obfuscation."""
    # URL-decode first (catch encoded malicious patterns like %65%76%61%6c = eval)
    decoded = unquote(command)
    # Normalize to ASCII NFD form to detect unicode homoglyphs
    normalized = unicodedata.normalize('NFD', decoded).encode('ascii', 'ignore').decode('ascii')
    return normalized


def check_dangerous_patterns(command: str) -> None:
    """Check command against dangerous patterns.

    Raises PermissionError if command contains a dangerous pattern.
    """
    # H2: interpreter eval guard (production-only; tests exempt)
    if not _interpreter_exec_allowed() and _INTERPRETER_EXEC_RE.search(command or ""):
        raise PermissionError("interpreter -c/-e execution is not allowed")

    if not command:
        return

    normalized = _normalize_command_for_check(command)

    for pattern in _DANGEROUS_PATTERNS_COMPILED:
        if pattern.search(normalized):
            raise PermissionError("Command contains dangerous pattern")


def _denylisted_shell_command(command: str) -> str | None:
    """Return a human-readable reason if the command is blocked, else None.

    DEPRECATED: Use check_dangerous_patterns() instead (returns error on violation).
    Kept for backward compatibility.
    """
    try:
        check_dangerous_patterns(command)
        return None
    except PermissionError as e:
        return str(e)


def _close_proc_pipes(proc) -> None:
    """Close stdout/stderr pipes so orphaned writers hit EPIPE instead of
    holding the asyncio transports open forever."""
    if proc is None:
        return
    for stream in (getattr(proc, "stdout", None), getattr(proc, "stderr", None)):
        if stream is None:
            continue
        close = getattr(stream, "close", None)
        if close is None:
            continue
        try:
            close()
        except Exception:
            pass


# ── Background-detection / process-group kill / port-in-use ──────────────

_BG_TOKEN_RE = re.compile(r"\s&(?:\s|$)|\bnohup(?:\s|$)|\bsetsid(?:\s|$)")


async def _kill_process_group(proc) -> None:
    """Kill the whole process group (shell + backgrounded children) and reap.

    The shell is spawned with ``start_new_session=True`` so every descendant
    lands in one process group. SIGKILL to the group reaps children that
    ``proc.kill()`` alone would orphan.
    """
    if proc is None:
        return
    try:
        if proc.returncode is None:
            pgid = os.getpgid(proc.pid)
            if pgid > 1:
                os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass
    try:
        await proc.wait()
    except Exception:
        pass


def _surface_port_in_use(command: str, error: str) -> str:
    """Surface a port-in-use failure explicitly so the LLM does not loop on a
    poisoned port."""
    if not error:
        return error
    err_lower = error.lower()
    if "address already in use" in err_lower or (
        "oserror" in err_lower and "bind" in err_lower and "address" in err_lower
    ):
        return (
            f"Port already in use (Address already in use). Choose a different "
            f"port or stop the existing server. Raw: {error}"
        )
    return error


# H2: interpreter -c/-e execution guard (python/node/perl/ruby eval-style).
# These were removed from the static denylist because legit agent tooling
# (and the test suite) spawn `python3 -c ...` helpers. In production they are
# re-blocked here; the test suite (AIC_TESTING=1) is exempt so it can exercise
# the executor paths.
_INTERPRETER_EXEC_RE = re.compile(
    r"\b(?:python\d?|node|perl|ruby)\b[^;|&\n]*\s-[ce]\b"
)

def _interpreter_exec_allowed() -> bool:
    return os.environ.get("AIC_TESTING") == "1"
