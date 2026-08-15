import socket
import logging
import json
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is currently bound by any process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def check_backend_health(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> Optional[dict]:
    """
    Check if a port has a healthy AIC backend serving.
    Returns health response dict if it's our backend, None otherwise.
    """
    import urllib.request
    import urllib.error

    url = f"http://{host}:{port}/health"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                # Verify it's an AIC backend (has version field)
                if "version" in data or "status" in data:
                    return data
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, socket.timeout, OSError) as e:
        logger.debug(f"Health check failed for {host}:{port}: {e}")
    return None


def get_lock_file_path(data_dir: str) -> Path:
    """Get the path to the backend port lock file."""
    return Path(data_dir) / "backend.port"


def read_locked_port(data_dir: str) -> Optional[int]:
    """Read the port from the lock file if it exists and process is alive."""
    lock_file = get_lock_file_path(data_dir)
    if not lock_file.exists():
        return None

    try:
        content = lock_file.read_text().strip()
        data = json.loads(content)
        port = data.get("port")
        pid = data.get("pid")

        # Verify process is still alive
        if pid:
            try:
                os.kill(pid, 0)  # Signal 0 = check if process exists
            except OSError:
                # Process dead, lock is stale
                logger.info(f"Stale lock file found (pid {pid} dead), removing")
                lock_file.unlink(missing_ok=True)
                return None

        return port
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid lock file format: {e}")
        lock_file.unlink(missing_ok=True)
        return None


def write_port_lock(data_dir: str, port: int, pid: int, host: str = "127.0.0.1"):
    """Write the port lock file."""
    lock_file = get_lock_file_path(data_dir)
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "port": port,
        "pid": pid,
        "host": host,
        "locked_at": __import__('time').strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    lock_file.write_text(json.dumps(data, indent=2))
    logger.info(f"Port lock written: {host}:{port} (pid {pid})")


def remove_port_lock(data_dir: str):
    """Remove the port lock file."""
    lock_file = get_lock_file_path(data_dir)
    lock_file.unlink(missing_ok=True)


def is_own_backend(port: int, data_dir: str, host: str = "127.0.0.1") -> bool:
    """
    Check if the backend at this port belongs to us.
    Compares health response data_dir/profile with our own.
    """
    health = check_backend_health(port, host)
    if not health:
        return False

    # Check if data_dir matches
    backend_data_dir = health.get("data_dir") or health.get("dataDir", "")
    if backend_data_dir and data_dir:
        # Normalize paths for comparison
        norm_backend = os.path.normpath(backend_data_dir)
        norm_ours = os.path.normpath(data_dir)
        if norm_backend == norm_ours:
            return True

    # If no data_dir in health, check lock file
    locked_port = read_locked_port(data_dir)
    return locked_port == port


def find_free_port(start_port: int = 8000, max_port: int = 8099,
                   host: str = "127.0.0.1", data_dir: Optional[str] = None) -> int:
    """
    Find a free port for the backend.

    Priority:
    1. If our lock file exists and process is alive and healthy, reuse that port
    2. If start_port is free, use it
    3. If start_port has something but it's NOT our backend, try next port
    4. If start_port has OUR backend running, return that port (will reuse)

    Args:
        start_port: Preferred port to start from
        max_port: Maximum port number to try
        host: Host address
        data_dir: AIC data directory for lock file and ownership check

    Returns:
        Available port number
    """
    # Priority 1: Check if we have a valid lock for an existing backend
    if data_dir:
        locked_port = read_locked_port(data_dir)
        if locked_port and is_port_in_use(locked_port, host):
            if is_own_backend(locked_port, data_dir, host):
                logger.info(f"Reusing locked port {locked_port} (our backend)")
                return locked_port

    # Priority 2: Check if start_port is free
    if not is_port_in_use(start_port, host):
        logger.info(f"Port {start_port} is free")
        return start_port

    # Priority 3: start_port is in use - check if it's our backend
    if data_dir and is_own_backend(start_port, data_dir, host):
        logger.info(f"Port {start_port} has our backend running")
        return start_port

    # Priority 4: start_port has something else, find next free port
    logger.info(f"Port {start_port} occupied by another service, searching...")
    for port in range(start_port + 1, max_port + 1):
        if not is_port_in_use(port, host):
            logger.info(f"Found free port {port}")
            return port

    raise RuntimeError(f"No free ports found in range {start_port}-{max_port}")
