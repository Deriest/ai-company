import subprocess
import time
import os
import sys
import logging
from pathlib import Path
from .port_manager import find_free_port
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
    try:
        port = find_free_port(start_port, 8099, host)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"Launching backend on {host}:{port}")
    
    # Get platform dir
    current_dir = Path(__file__).parent.parent.parent.resolve()
    
    env = os.environ.copy()
    env["AIC_DATA_DIR"] = data_dir
    env["PYTHONPATH"] = str(current_dir)
    
    # We use subprocess.Popen to start uvicorn
    # In a real environment, this might be handled by Electron spawning Python
    # But this script can be used as a standalone entry point if needed
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
        write_runtime_state(host, port, process.pid, data_dir)
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
    process, url = launch_backend(args.data_dir)
    
    # Wait for process
    process.wait()
