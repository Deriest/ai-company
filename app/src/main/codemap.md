# AI Company ADE - Main Process Codemap

## Directory Responsibility

This directory contains the **Electron main process implementation** for the AI Company AI Development Environment (ADE). It serves as the bridge between Electron's native capabilities and the application's frontend, handling:

- **Application lifecycle management**: Window creation, single-instance lock, graceful shutdown
- **Backend orchestration**: Spawning and managing the Python-based backend server (sidecar architecture)
- **Security enforcement**: Navigation guards, path validation, environment variable filtering
- **IPC handler registration**: Exposing safe APIs to the renderer process via `ipcMain`
- **Desktop identity management**: Per-install credential generation and persistence
- **Auto-update system**: Platform-specific update check/download/install logic with cryptographic verification
- **Backup/restore operations**: Atomic data directory swaps with rollback capability
- **Terminal emulation**: PTY-based interactive shell support

---

## Design Patterns

### 1. Singleton / Service Locator Pattern
```typescript
// Module-level state acts as shared service registry
let mainWindow: BrowserWindow | null = null;
let updateManager: UpdateManager | null = null;
let backendProc: ChildProcessWithoutNullStreams | null = null;
```

### 2. Dependency Injection
The `UpdateManager` accepts injected I/O and app adapters for testability:
```typescript
constructor(
  config?: Partial<UpdateConfig> | Partial<IO>,
  io?: Partial<IO> | Partial<AppAdapter>,
  appAdapter?: Partial<AppAdapter>
)
```

### 3. Observer Pattern
```typescript
type UpdateListener = (state: UpdateState) => void;
private listeners = new Set<UpdateListener>();

on(listener: UpdateListener): () => void {
  this.listeners.add(listener);
  return () => this.listeners.delete(listener);
}
```

### 4. Async Lock / Mutual Exclusion
```typescript
let backupLockPromise: Promise<void> | null = null;

async function acquireBackupLock(): Promise<() => Promise<void>> {
  if (backupLockPromise) await backupLockPromise;
  backupLockPromise = Promise.resolve();
  return async () => { backupLockPromise = null; };
}
```

### 5. Factory Pattern
Directory resolution adapts to dev/packaged environments:
```typescript
export function resolvePlatformDir(): string {
  // Packaged: resources/backend
  // Dev: sibling monorepo directory
  // Fallback: workspace-relative paths
}
```

### 6. Strategy Pattern
Python runtime resolution tries multiple strategies:
1. Packaged portable Python (`resources/python-win/linux`)
2. Packaging root for development builds
3. Platform-local virtualenv
4. System Python (dev only)

### 7. Guard Pattern
```typescript
export function isAllowedNavigation(
  url: string,
  distDir: string,
  allowDevServer: boolean
): boolean {
  // Returns false by default; explicit allowlists only
}
```

### 8. Circuit Breaker Pattern
Backend restart attempts limited to 3 retries before stopping:
```typescript
if (restartAttempts < 3) {
  setTimeout(() => void ensureBackendRunning(), 2000);
}
```

---

## Data & Control Flow

### Application Startup Sequence

```mermaid
graph TD
    A[app.whenReady()] --> B[nativeTheme.themeSource = 'dark']
    B --> C[ensureAppData()]
    C --> D[loadOrCreateIdentity]
    D --> E[readStore projectRoot]
    E --> F[initUpdateManager]
    F --> G[registerIpc handlers]
    G --> H[createWindow]
    H --> I[load index.html / Vite dev]
    I --> J[ensureBackendRunning]
    J --> K[Poll health endpoint]
    K --> L{Healthy?}
    L -->|Yes| M[start complete]
    L -->|No| N[error state + retry loop]
```

### Backend Sidecar Lifecycle

```typescript
// Phase 1: Health check
async function checkBackendHealth(): Promise<boolean> {
  const res = await fetch(`http://127.0.0.1:${backendPort}/health`);
  return res.ok;
}

// Phase 2: Spawn sidecar
backendProc = spawn(pythonPath, ["-m", "uvicorn", "backend.main:app", ...], {
  cwd: platformDir,
  env: filteredEnv  // Only whitelisted variables
});

// Phase 3: Monitor logs for "Uvicorn running on"
backendProc.stdout.on("data", (chunk) => {
  if (text.includes("Uvicorn running on")) {
    backendStatus = "healthy";
    writeRuntimeState(port, pid);
  }
});

// Phase 4: Auto-restart on crash (max 3 attempts)
backendProc.on("exit", (code) => {
  if (restartAttempts < 3) setTimeout(restart, 2000);
});
```

### IPC Communication Flow

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `aic:get-identity` | main → renderer | Return per-install credentials |
| `aic:store-get/set` | main ↔ renderer | Persist configuration (sanitized) |
| `aic:select-directory` | main → renderer | Open native dialog for project selection |
| `aic:read-dir-tree` | main → renderer | Recursive directory listing (filtered) |
| `aic:term-start/write/kill` | main ↔ renderer | PTY terminal session control |
| `aic:update-*` | main ↔ renderer | Auto-update state queries |
| `aic:backup-create-to` | main → renderer | Export backup archive |
| `aic:backup-restore` | main → renderer | Import backup with atomic swap |

### Backup/Restore Flow

```typescript
// CREATE (POST /backup/create from renderer via token)
→ backendPost("/backup/create")
→ saves zip to backupsDir()

// RESTORE
dialog.showOpenDialog(zipFile)
  ↓
extractBackupZip(zipPath, tempDir)     # Python zipfile with zip-slip guard
  ↓
verifyBackupContents(root)             # Check manifest.json + snapshot.db
  ↓
stopBackend()                          # SIGTERM + wait for exit
  ↓
renameSync(appDataDir, preRestoreDir)  # Safety copy
  ↓
renameSync(dataRoot entries → appDataDir)  # Atomic move
  ↓
ensureBackendRunning()                 # Restart sidecar
```

### Security Boundary Enforcement

```typescript
// Path validation: extraRoots (project) + dataRoots (userData)
export function resolveSafe(target: string, extraRoots, dataRoots): string {
  const resolved = path.resolve(target);
  const ok = roots.some(root => 
    resolved === root || resolved.startsWith(root + path.sep)
  );
  if (!ok) throw new Error(`path not allowed: ${resolved}`);
  
  // Symlink escape detection
  const real = fs.realpathSync(resolved);
  if (real !== resolved) {
    // Verify symlink target also inside roots
  }
  return resolved;
}

// Environment filter before spawning backend
const allowedEnvVars = new Set([
  'PYTHONPATH', 'PYTHONUNBUFFERED', 'AIC_DATA_DIR',
  'AIC_IDENTITY_FILE', 'AIC_JWT_SECRET', 'CI'
]);
const filteredEnv = {};
for (const [key, value] of Object.entries(process.env)) {
  if (allowedEnvVars.has(key) && value) filteredEnv[key] = value;
}
```

---

## Integration Points

### 1. Backend Sidecar API

Communicates via HTTP on localhost:8000+:
```typescript
GET http://127.0.0.1:{port}/health      # Readiness probe
POST http://127.0.0.1:{port}/backup/create   # Trigger backup creation
```

Environment variables passed:
- `AIC_DATA_DIR`: App data directory path
- `AIC_IDENTITY_FILE`: Credentials JSON location
- `AIC_JWT_SECRET`: Required for authentication
- `PYTHONPATH`: Platform directory

### 2. Frontend Renderer

Via preload script's exposed `window.electronAPI`:
```typescript
// File access
await window.electronAPI['aic:read-dir-tree'](dir, maxDepth)
await window.electronAPI['aic:open-path'](path)

// Terminal
await window.electronAPI['aic:term-start'](cwd)
window.electronAPI['aic:term-write'](data)

// Updates
await window.electronAPI['aic:update-check']()
await window.electronAPI['aic:update-download']()
window.addEventListener('aic:update-state-changed', handler)
```

### 3. Auto-Update Server

Manifest URL pattern:
```typescript
manifestUrl(baseUrl, channel)  // e.g., https://github.com/user/releases/latest/download/aic-ade-manifest.json
```

Supported platforms in manifest:
- `darwin`: .dmg installer (macOS)
- `win32`: .exe installer (Windows)
- `linux`: .AppImage (Linux)

Verification flow:
1. Fetch `manifest.json` + `manifest.json.sig` (ed25519 signature)
2. Call `verifyManifestSignature(raw, signature)`
3. If signature missing, check deployment status

### 4. Native Dialog Services

```typescript
// Project selection
dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] })

// Backup export
dialog.showSaveDialog({ filters: [{ name: "Backup Archive", extensions: ["zip"] }] })

// Restore import
dialog.showOpenDialog({ filters: [{ name: "Backup Archive", extensions: ["zip"] }] })
```

### 5. Platform-Specific Integrations

#### macOS
- Keep app alive on `window-all-closed` (activate from dock)
- Use `.dmg` opening for updates
- No backend kill on quit

#### Windows
- Single instance focuses existing window
- Batch script wrapper for installers (with 2s delay)
- Kill all processes on exit

#### Linux
- AppImage execution with filename sanitization
- Standard XDG behavior on close

---

## Key Files Reference

| File | Lines | Primary Concern |
|------|-------|-----------------|
| `main.ts` | 1146 | Entry point, backend spawning, IPC registration |
| `security.ts` | 142 | Path validation, navigation guards, port scanning |
| `updateConfig.ts` | 13 | Config re-export, base URL resolution |
| `updateManager.ts` | 703 | Auto-update orchestration with crypto verification |

---

## Security Considerations

1. **JWT Secret Required**: Production always requires `AIC_JWT_SECRET` env var
2. **Environment Whitelist**: Only explicitly allowed vars pass to backend
3. **Path Sanitization**: All user-provided paths validated against SENSITIVE_FS_ROOTS
4. **Symlink Escape Prevention**: realpath() validation on every access
5. **CSP Headers**: Restrict resource loading to self + local engine
6. **Navigation Guards**: Reject arbitrary file:// URLs and remote pages
7. **Installer Filename Sanitization**: Reject shell metacharacters in update artifacts
8. **Manifest Signature Verification**: ed25519 crypto check before trust

---

## Concurrency Safety

- **Backup lock**: Async lock prevents concurrent restore operations
- **Single instance lock**: Prevents dual backend spawns
- **Backend restart gating**: `isQuitting` flag prevents auto-restart during shutdown
- **Atomic writes**: Temp file rename pattern for `state.json` integrity

---

## Observability

Logs written to `$APPDATA/aic-ade/logs/backend-startup.log`

Key traceable states:
- `backendStatus`: stopped → starting → healthy / error
- `restartAttempts`: tracks automatic recovery tries
- `updateManager.state`: current update pipeline phase

---

*Generated: 2026-08-10*  
*Based on: main.ts, security.ts, updateConfig.ts, updateManager.ts*
