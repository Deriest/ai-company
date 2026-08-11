"""Application-wide constants and configuration.

Centralized numeric constants that were previously scattered as magic numbers.
This improves maintainability and allows runtime overrides where appropriate.
"""

# Database lock retry parameters (used in lock_retry.py, metrics.py, provider.py)
DB_LOCK_RETRY_ATTEMPTS = 6
DB_LOCK_BASE_DELAY = 0.05

# HTTP timeouts (ms)
HTTP_TIMEOUT_MS = 120000  # 120 seconds for LLM requests
API_REQUEST_TIMEOUT = 30  # 30 seconds for API calls

# SQLite configuration
SQLITE_BUSY_TIMEOUT_MS = 30000  # 30 seconds busy timeout
SQLITE_CONNECTION_POOL_SIZE = 5
SQLITE_MAX_OVERFLOW = 10
SQLITE_CONNECTION_RECYCLE_SECONDS = 3600  # 1 hour

# Worker lease configuration (runtime/executor.py)
DEFAULT_WORKER_LEASE_TIMEOUT_MINUTES = 30
ADAPTIVE_TIMEOUT_MULTIPLIERS = {
    "thinker": 2.5,
    "crafter": 2.5,
    "sprinter": 1.5,
}

# Usage tracking limits
USAGE_TRACKER_MAX_RECORDS = 10000
USAGE_TRACKER_RETENTION_SAMPLES = 5000

# Concurrency limits
LLM_MAX_CONCURRENT_REQUESTS = 4
AGENT_RUN_SEMAPHORE_LIMIT = 2

# Metric retention
METRIC_QUERY_LIMIT = 100
METRIC_AVERAGE_WINDOW_DAYS = 30

# Discovery/session management
CLARIFY_QUESTION_LIMIT = 10
DISCOVERY_SESSION_HISTORY_LIMIT = 50

# File system limits
MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
WORKSPACE_PATH_REGEX_PATTERN = r"((?:[A-Za-z]:[/\\][^\s\"'<>|?*]+)|(?:/ [^\s\"'<>|?*]+))"

# Logging levels
LOG_ERROR_THRESHOLD = "ERROR"
LOG_WARNING_THRESHOLD = "WARNING"
