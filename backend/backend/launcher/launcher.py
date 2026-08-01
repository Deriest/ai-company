import subprocess
import time
import os
import sys
import signal
import logging
from pathlib import Path
from .port_manager import find_free_port, write_port_lock, remove_port_lock, check_backend_health
from .runtime_state import write_runtime_state
import requests

logger = logging.getLogger(__name__)

def check_health(url: str, timeout: int = 30) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def launch_backend(data_dir: str, host: str = "127.0.0.1", start_port: int = 8000):
    """
    Launch the backend with smart port management.
    
    Port selection logic:
    1. If our backend is already running (lock file + health check), reuse it
    2. If start_port is free, use it
    3. If start_port has another service, find next free port
    
    This prevents port-hopping when stale backends exist.
    """
    try:
        # Use smart port finder with data_dir for lock file awareness
        port = find_free_port(start_port, 8099, host, data_dir=data_dir)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    # Check if our backend is already healthy on this port
    health = check_backend_health(port, host)
    if health:
        url = f"http://{host}:{port}"
        logger.info(f"Backend already running at {url} (version: {health.get('version', 'unknown')})")
        
        # Verify it's healthy and update lock file
        write_port_lock(data_dir, port, health.get("pid", os.getpid()), host)
        write_runtime_state(host, port, health.get("pid", os.getpid()), data_dir)
        
        # Return None for process since it's already running
        return None, url

    logger.info(f"Launching backend on {host}:{port}")
    
    # Get platform dir
    current_dir = Path(__file__).parent.parent.parent.resolve()
    
    env = os.environ.copy()
    env["AIC_DATA_DIR"] = data_dir
    env["PYTHONPATH"] = str(current_dir)
    
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", host, "--port", str(port)]
    
    process = subprocess.Popen(
        cmd,
        cwd=str(current_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    url = f"http://{host}:{port}"
    if check_health(url):
        logger.info("Backend is healthy")
        
        # Write port lock to prevent port-hopping
        write_port_lock(data_dir, port, process.pid, host)
        write_runtime_state(host, port, process.pid, data_dir)
        
        # Register cleanup handler to remove lock on exit
        def cleanup_handler(signum=None, frame=None):
            logger.info("Cleaning up backend lock...")
            remove_port_lock(data_dir)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            if signum is not None:
                sys.exit(0)
        
        signal.signal(signal.SIGTERM, cleanup_handler)
        signal.signal(signal.SIGINT, cleanup_handler)
        
        return process, url
    else:
        logger.error("Backend failed to become healthy")
        process.kill()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    result = launch_backend(args.data_dir)
    
    if result[0] is not None:
        # Wait for process
        result[0].wait()
    else:
        print(f"Backend already running at {result[1]}")
