"""Error recovery service with retry logic for transient failures."""
import asyncio
import logging
import os
from typing import Optional, Callable, Any, TypeVar
from functools import wraps

logger = logging.getLogger("aic.error_recovery")

T = TypeVar('T')


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.last_error = last_error


async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable[..., T]:
    """Decorator for automatic retry with exponential backoff.

    Args:
        func: Async function to wrap
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        backoff_factor: Multiplier for each retry
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Wrapped async function with retry logic
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        last_error = None
        current_delay = initial_delay

        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except retryable_exceptions as e:
                last_error = e
                logger.warning(f"Retryable error (attempt {attempt + 1}/{max_retries + 1}): {e}")

                if attempt < max_retries:
                    await asyncio.sleep(current_delay)
                    current_delay = min(current_delay * backoff_factor, max_delay)
                else:
                    raise RetryError(
                        f"All {max_retries} retry attempts failed",
                        last_error=last_error
                    )

        raise RetryError("Unexpected retry loop completion", last_error=last_error)

    return wrapper


def create_error_handler(error_type: str) -> dict:
    """Create structured error handler configuration.

    Args:
        error_type: Type of error handler ('network', 'filesystem', 'llm', etc.)

    Returns:
        Dict with retry config and error mapping
    """
    configs = {
        "network": {
            "max_retries": 3,
            "initial_delay": 1.0,
            "max_delay": 10.0,
            "retryable": (TimeoutError, ConnectionError, OSError),
        },
        "filesystem": {
            "max_retries": 2,
            "initial_delay": 0.5,
            "max_delay": 5.0,
            "retryable": (PermissionError, FileNotFoundError, IsADirectoryError),
        },
        "llm": {
            "max_retries": 5,
            "initial_delay": 2.0,
            "max_delay": 30.0,
            "retryable": (ConnectionError, TimeoutError, Exception),
        },
        "shell": {
            "max_retries": 2,
            "initial_delay": 1.0,
            "max_delay": 5.0,
            "retryable": (OSError,),
        },
    }
    return configs.get(error_type, configs["network"])


class ErrorRecoveryService:
    """Centralized error handling with retry logic and recovery strategies."""

    def __init__(self):
        self.recovery_stats = {}
        self._registered_handlers = {}

    def register_handler(self, error_type: str, handler: Callable):
        """Register custom error handler for specific error type."""
        self._registered_handlers[error_type] = handler

    async def handle_with_recovery(
        self,
        operation: str,
        func: Callable,
        error_type: str = "default",
        **kwargs
    ) -> tuple[bool, Any, Optional[str]]:
        """Execute operation with full error recovery.

        Returns:
            Tuple of (success: bool, result: Any, error_message: str | None)
        """
        config = create_error_handler(error_type)

        try:
            result = await retry_with_backoff(
                func,
                max_retries=config["max_retries"],
                initial_delay=config["initial_delay"],
                max_delay=config["max_delay"],
                retryable_exceptions=config["retryable"],
            )(*kwargs.get("args", ()), **kwargs.get("kwargs", {}))

            # Track success
            key = f"{operation}:success"
            self.recovery_stats[key] = self.recovery_stats.get(key, 0) + 1

            return True, result, None

        except RetryError as e:
            # Track failure
            key = f"{operation}:failure:retry_exhausted"
            self.recovery_stats[key] = self.recovery_stats.get(key, 0) + 1

            # Check for custom handler
            if error_type in self._registered_handlers:
                custom_result = self._registered_handlers[error_type](e)
                return False, custom_result, str(e.last_error)

            return False, None, f"Operation '{operation}' failed after retries: {e.last_error}"

        except Exception as e:
            # Non-retryable error
            key = f"{operation}:failure:{type(e).__name__}"
            self.recovery_stats[key] = self.recovery_stats.get(key, 0) + 1

            return False, None, str(e)

    def get_stats(self) -> dict:
        """Get recovery statistics."""
        return dict(self.recovery_stats)

    def reset_stats(self):
        """Reset all statistics."""
        self.recovery_stats.clear()


try:
    import psutil
except ImportError:
    psutil = None

def get_process_memory_usage() -> dict | None:
    """Get current process memory usage for monitoring."""
    if not psutil:
        return None
    try:
        p = psutil.Process(os.getpid())
        m = p.memory_info()
        return {"rss_mb": m.rss/1024/1024, "vms_mb": m.vms/1024/1024}
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.warning(f"Failed to get process memory usage: {e}")
        return None
    except Exception as e:
        # Log unexpected errors but don't swallow shutdown signals (KeyboardInterrupt, SystemExit)
        logger.warning(f"Unexpected error getting process memory: {e}", exc_info=True)
        return None


def log_mem(tag: str):
    """Log memory usage."""
    u = get_process_memory_usage()
    if u:
        logger.info(f"[MEM {tag}] RSS: {u['rss_mb']:.1f}MB VMS: {u['vms_mb']:.1f}MB")
