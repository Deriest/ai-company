"""Shell security imports centralized from backend.security.shell_security."""
from backend.security.shell_security import (
    check_dangerous_patterns,
    _denylisted_shell_command,
    _close_proc_pipes,
)


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
