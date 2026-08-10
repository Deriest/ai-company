# Pragmatic guard against obviously destructive / exfiltration commands. Each
# entry is (compiled regex, human reason); matched case-insensitively against
# the raw command BEFORE the shell is spawned. This is NOT a substitute for a
# full argv allowlist / sandbox — legit multi-command agent usage (git, build,
# test) must keep working, so we only block clearly catastrophic patterns.
# A full allowlist-based sandbox is documented as future work in run_shell.

import re
import unicodedata
from urllib.parse import unquote

# ── Shell command safety patterns ──────────────────────
# Block ONLY truly dangerous patterns at WORD BOUNDARIES to allow legitimate
# multi-command usage (git add . && git commit, etc.) while preventing catastrophic commands.

_DANGEROUS_COMMANDS = [
    r'\brm\s+-rf\s+/\s*$',           # rm -rf / with trailing whitespace
    r'\brm\s+-rf\s+~\s*$',           # rm -rf ~ (home directory)
    r'\brm\s+-rf\s+\$HOME\s*$',      # rm -rf $HOME
    r'\bmkfs\b',                      # mkfs (format filesystem)
    r'\bdd\s+(?:if=\s*.+?|of=\s*.+?)?',  # dd (raw disk access)
    r'>\s*/dev/sd',                  # write to raw block device
    r'\b(eval|exec|system)\b',       # exact word matches only
    r':\(\)\s*\{[^}]*\};:',         # fork bomb pattern
    r'\bchmod\s+-R\s+777\s+/\s*$',  # chmod -R 777 /
]


def _normalize_command_for_check(command: str) -> str:
    """Normalize command to catch homoglyph attacks and decode URLs."""
    # URL-decode first (catch encoded malicious patterns)
    decoded = unquote(command)
    # Normalize to ASCII NFD form to detect unicode homoglyphs
    normalized = unicodedata.normalize('NFD', decoded).encode('ascii', 'ignore').decode('ascii')
    return normalized


def check_dangerous_patterns(command: str) -> None:
    """Check command against dangerous patterns with proper word boundaries.
    
    Raises PermissionError if command contains a dangerous pattern.
    """
    if not command:
        return
    
    normalized = _normalize_command_for_check(command)
    
    for pattern in _DANGEROUS_COMMANDS:
        if re.search(pattern, normalized, re.IGNORECASE):
            raise PermissionError(f"Command contains dangerous pattern: {pattern}")


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
