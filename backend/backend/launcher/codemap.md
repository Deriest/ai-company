# Launcher Module Codemap

## 1. Responsibility

The `launcher` module serves as the **orchestrator and lifecycle manager** for the AIC backend service. Its primary responsibilities include:

- **Process Management**: Launching, monitoring, and terminating the backend uvicorn server process
- **Port Orchestration**: Smart port selection to prevent conflicts and "port-hopping" when stale backends exist
- **State Persistence**: Tracking backend runtime state (host, port, PID) via lock files and JSON state files
- **Health Verification**: Ensuring the backend is healthy before proceeding with requests
- **Cleanup Coordination**: Registering signal handlers to properly clean up locks and terminate processes on exit

This module acts as the entry point for starting the application and ensuring a consistent, reliable backend deployment.

---

## 2. Design Patterns

### 2.1 Port Manager Pattern (`port_manager.py`)

```python
def find_free_port(start_port: int, max_port: int, host: str, data_dir: Optional[str] = None) -> int
```

A smart port allocation strategy that prioritizes:
1. Reusing an existing valid locked port from a previous session
2. Using the preferred start port if available
3. Finding the next free port in range [start_port, max_port]
4. Detecting and reclaiming stale locks (orphaned processes)

### 2.2 Health Check Pattern

```python
def check_health(url: str, timeout: int = 30) -> bool
def check_backend_health(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> Optional[dict]
```

Two-tier health verification:
- **Polling-based**: Repeatedly checks `/health` endpoint with exponential retry logic
- **Validation**: Confirms health response contains expected fields (`version`, `status`, `data_dir`)

### 2.3 Lock File Pattern

Lock file at `{data_dir}/backend.port`:
```json
{
  "port": 8000,
  "pid": 12345,
  "host": "127.0.0.1",
  "locked_at": "2026-08-10T12:00:00Z"
}
```

Provides:
- Process ownership tracking
- Stale lock detection via PID liveness check (`os.kill(pid, 0)`)
- Prevention of port collisions between multiple launcher instances

### 2.4 Runtime State Pattern (`runtime_state.py`)

State file at `{data_dir}/runtime.json`:
```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "url": "http://127.0.0.1:8000",
  "pid": 12345,
  "started_at": "2026-08-10T12:00:00Z"
}
```

Immutable timestamp recording of when the backend was started, enabling audit trails.

### 2.5 Signal Handler Pattern (`launcher.py` lines 87-100)

Graceful shutdown via SIGTERM/SIGINT registration:
```python
def cleanup_handler(signum=None, frame=None):
    remove_port_lock(data_dir)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    if signum is not None:
        sys.exit(0)
```

Ensures lock file removal and proper process termination even on forced shutdown.

### 2.6 Factory Method Pattern

`launch_backend()` acts as a factory that returns either:
- `(None, url)` - Backend already running (reused instance)
- `(process, url)` - New backend launched successfully

---

## 3. Data & Control Flow

### 3.1 Main Launch Flow (`launcher.py`)

```
┌─────────────────────────────────────────────────────────────┐
│                   launch_backend()                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Call find_free_port(data_dir)                           │
│     └─> Reads lock file → checks process liveness          │
│         └─> Checks health endpoint → validates ownership   │
│                                                             │
│  2. Check backend health on selected port                  │
│     └─> If healthy:                                        │
│          • Update lock file                                │
│          • Write runtime_state                             │
│          • Return (None, url)                              │
│                                                             │
│  3. Launch subprocess                                      │
│     └─> Set env vars: AIC_DATA_DIR, PYTHONPATH             │
│     └─> Execute: uvicorn backend.main:app --host --port   │
│                                                             │
│  4. Poll /health endpoint until healthy                    │
│     └─> On success:                                        │
│          • Register signal handlers                        │
│          • Write lock + state files                        │
│          • Return (process, url)                           │
│     └─> On failure: kill process + exit                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Port Resolution Logic (`port_manager.py::find_free_port`)

```
Priority Order:
┌──────────────────────────────────────────────────────────┐
│ P1: Locked port exists AND process alive AND healthy     │
│     └─> RETURN locked_port                               │
├──────────────────────────────────────────────────────────┤
│ P2: start_port is FREE                                   │
│     └─> RETURN start_port                                │
├──────────────────────────────────────────────────────────┤
│ P3: start_port has OUR backend (via lock + health)       │
│     └─> RETURN start_port                                │
├──────────────────────────────────────────────────────────┤
│ P4: Scan [start_port+1, max_port] for free port          │
│     └─> RETURN first free port OR raise RuntimeError    │
└──────────────────────────────────────────────────────────┘
```

### 3.3 Health Validation Chain

```
check_health() → urllib.request.urlopen(/health)
       │
       ├─> HTTP 200? → NO → Retry (sleep 0.5s)
       │
       └─> YES → Parse JSON → Check required fields
                      │
                      ├─> Has 'version' or 'status'? → YES → Healthy
                      │
                      └─> Has 'data_dir' → Compare with local data_dir
                                     │
                                     └─> Match? → Own backend confirmed
```

### 3.4 State File Lifecycle

```
Write Phase:
  write_port_lock()    → {data_dir}/backend.port (writable lock)
  write_runtime_state()→ {data_dir}/runtime.json (immutable history)

Read Phase:
  read_locked_port()   → Validate PID liveness → Return port or None
  check_backend_health() → Verify health endpoint → Return dict or None
```

### 3.5 Cleanup Sequence (Signal Handler)

```
SIGTERM/SIGINT received
       │
       ├─> Log cleanup message
       ├─> remove_port_lock(data_dir)
       ├─> process.terminate() (graceful)
       │     └─> Wait timeout=5s
       │           └─> Timeout → process.kill() (force)
       └─> sys.exit(0)
```

---

## 4. Integration Points

### 4.1 Dependencies (Import Tree)

```
launcher/
├── launcher.py
│   ├── .port_manager
│   │   ├── socket (system calls)
│   │   ├── json (serialization)
│   │   ├── os (file system, signals)
│   │   ├── pathlib.Path
│   │   └── typing.Optional
│   ├── .runtime_state
│   │   ├── json
│   │   ├── os
│   │   ├── time
│   │   └── pathlib.Path
│   ├── subprocess (Popen for uvicorn)
│   ├── signal (register handlers)
│   ├── logging
│   ├── time
│   ├── requests (HTTP health checks)
│   ├── sys (exit codes)
│   └── argparse (CLI args)
└── __init__.py (assumed, exposes launcher, port_manager, runtime_state)
```

### 4.2 External Services

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Backend API | `GET /health` | Verify uvicorn server is serving |
| System Kernel | `socket.connect_ex()` | TCP port availability check |
| System Kernel | `os.kill(pid, 0)` | Process liveness check |

### 4.3 Consumed By

| Consumer | Usage |
|----------|-------|
| CLI entry script (not shown) | Calls `launch_backend(data_dir)` from `__main__` |
| Deployment scripts | Import `find_free_port`, `check_backend_health` directly |
| Other modules | May read `runtime.json` for runtime discovery |

### 4.4 Produced Artifacts

| Artifact | Location | Owner |
|----------|----------|-------|
| `backend.port` | `{data_dir}/` | Lock manager (writable, removed on exit) |
| `runtime.json` | `{data_dir}/` | Runtime tracker (appended on each launch) |
| `/var/log/aic/` | (external) | Backend stdout/stderr piped here |

### 4.5 Environment Variables Required

| Variable | Value | Source |
|----------|-------|--------|
| `AIC_DATA_DIR` | Path to app data directory | Passed to child process |
| `PYTHONPATH` | Absolute workspace path | Computed from launcher location |

### 4.6 Command-Line Interface

```bash
python -m launcher.launcher --data-dir <path>
```

Arguments:
- `--data-dir` (required): Application data directory for lock/state files

Function signature:
```python
launch_backend(
    data_dir: str,
    host: str = "127.0.0.1",
    start_port: int = 8000
) -> Tuple[Optional[subprocess.Popen], str]
```

---

## 5. Key Constants

| Name | Default | Purpose |
|------|---------|---------|
| `start_port` | `8000` | Preferred listening port |
| `max_port` | `8099` | Upper bound for port search |
| `timeout` | `30s` | Maximum health check wait time |
| `health_timeout` | `2s` | Per-request health check timeout |
| `signal_wait` | `5s` | Graceful termination timeout |

---

## 6. Error Handling Strategies

| Scenario | Detection | Recovery Action |
|----------|-----------|-----------------|
| No free ports | Exhausted range scan | Raise `RuntimeError` + exit |
| Stale lock file | `os.kill(pid, 0)` fails | Delete lock, treat as fresh |
| Corrupt lock JSON | `json.JSONDecodeError` | Delete corrupt file |
| Backend unhealthy | Health check timeout | Kill process + exit |
| Termination timeout | `TimeoutExpired` | Force `kill()` |
| Signal interruption | `SIGTERM/SIGINT` | Run cleanup handler |

---

## 7. Files Summary

| File | Lines | Core Functions | Primary Role |
|------|-------|----------------|--------------|
| `launcher.py` | 122 | `launch_backend`, `check_health` | Process orchestration |
| `port_manager.py` | 162 | `find_free_port`, `is_own_backend` | Port allocation & validation |
| `runtime_state.py` | 22 | `write_runtime_state` | State persistence |

**Total**: 3 files, 306 lines of Python code

---

*Generated by Codemap Skill Analysis*
