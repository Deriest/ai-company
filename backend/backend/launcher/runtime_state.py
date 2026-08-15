import json
import time
from pathlib import Path

def write_runtime_state(host: str, port: int, pid: int, data_dir: str):
    state = {
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "pid": pid,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    # Store in app data dir
    runtime_file = Path(data_dir) / "runtime.json"
    runtime_file.parent.mkdir(parents=True, exist_ok=True)

    with open(runtime_file, "w") as f:
        json.dump(state, f, indent=2)

    return runtime_file
