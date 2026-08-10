"""AIC Platform — Shell command security patterns.

Shared denylist for shell commands with defense-in-depth protections.
This is NOT a substitute for sandboxing — only blocks clearly catastrophic patterns.

CRITICAL: This module consolidates previously duplicated denylists from tool_executor.py
and workers/tools.py into a single source of truth.
"""
import re
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
    r'\bpython\s+-[cC]\s+',                 # python -c "..."
    r'\bbash\s+-c\s+',                      # bash -c "..."
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
    if not command:
        return
    
    normalized = _normalize_command_for_check(command)
    
    for pattern in _DANGEROUS_PATTERNS_COMPILED:
        if pattern.search(normalized):
            raise PermissionError(f"Command contains dangerous pattern")


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
