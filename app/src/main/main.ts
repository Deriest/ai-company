import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  shell,
  nativeTheme,
} from "electron";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import * as pty from "node-pty";
import { UpdateManager } from "./updateManager";
import {
  defaultUpdateConfig,
  resolveUpdateBaseUrl,
  DEFAULT_UPDATE_BASE_URL,
  type UpdateConfig,
} from "./updateConfig";
import { findFreePort, isAllowedNavigation, sanitizeProjectRoot, resolveSafe } from "./security";

const isDev = !app.isPackaged && process.env.AIC_IDE_DEV === "1";

// Async lock for backup/restore operations (prevents concurrent restores)
let backupLockPromise: Promise<void> | null = null;
let backupLockResolve: (() => void) | null = null;

/**
 * Acquire async lock to prevent concurrent backup/restore operations.
 * Returns unlock function that must be called when done.
 * Concurrent callers await the previous holder's unlock before proceeding.
 */
async function acquireBackupLock(): Promise<() => Promise<void>> {
    while (backupLockPromise) {
        await backupLockPromise;
    }
    let resolve!: () => void;
    backupLockPromise = new Promise<void>((r) => { resolve = r; });
    backupLockResolve = resolve;

    const unlock: () => Promise<void> = async () => {
        const r = backupLockResolve;
        backupLockPromise = null;
        backupLockResolve = null;
        if (r) r();
    };

    return unlock;
}

type DirTreeNode = {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: DirTreeNode[];
};

function appDataDir(): string {
  return path.join(app.getPath("userData"), "aic-ade");
}

/** Per-install desktop credential — generated once, persisted to userData,
 *  and shared with the backend via AIC_IDENTITY_FILE. Never regenerated, so
 *  the stored token survives restarts. chmod 600 (no-op on Windows). */
function loadOrCreateIdentity(): { username: string; password: string } {
  const p = path.join(appDataDir(), "identity.json");
  if (fs.existsSync(p)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(p, "utf8"));
      if (parsed && typeof parsed.username === "string" && parsed.username
          && typeof parsed.password === "string" && parsed.password) {
        return { username: parsed.username, password: parsed.password };
      }
    } catch {
      /* corrupted file — regenerate */
    }
  }
  const identity = {
    username: "admin",
    password: crypto.randomBytes(32).toString("hex"),
  };
  fs.writeFileSync(p, JSON.stringify(identity, null, 2), { mode: 0o600 });
  try {
    fs.chmodSync(p, 0o600);
  } catch {
    /* Windows: no chmod */
  }
  return identity;
}

function ensureAppData(): void {
  const dir = appDataDir();
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const downloads = path.join(dir, "downloads");
  if (!fs.existsSync(downloads)) fs.mkdirSync(downloads, { recursive: true });
  // Scrub legacy web-era secrets from persisted store. The JWT is memory-only
  // (never persisted), so clean up any token a previous release wrote to disk.
  try {
    const store = readStore();
    if ("password" in store || "token" in store) {
      delete store.password;
      delete store.token;
      writeStore(store);
    }
  } catch {
    /* ignore */
  }
}

/** Write runtime.json so the frontend can read the chosen port on startup. */
function writeRuntimeState(port: number | null, pid: number | null): void {
  if (!port) return;
  const state = {
    host: "127.0.0.1",
    port,
    url: `http://127.0.0.1:${port}`,
    pid: pid ?? null,
    started_at: new Date().toISOString(),
  };
  try {
    fs.writeFileSync(
      path.join(appDataDir(), "runtime.json"),
      JSON.stringify(state, null, 2),
      "utf8"
    );
  } catch {
    /* ignore */
  }
  backendPort = port;
}

function storePath(): string {
  return path.join(appDataDir(), "state.json");
}

function readStore(): Record<string, unknown> {
  try {
    return JSON.parse(fs.readFileSync(storePath(), "utf8"));
  } catch {
    return {};
  }
}

function writeStore(data: Record<string, unknown>): void {
  ensureAppData();
  // M7: atomic write — write to a temp file then rename over the target so a
  // crash mid-write never leaves a truncated state.json.
  const tmpPath = storePath() + ".tmp";
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), "utf8");
  fs.renameSync(tmpPath, storePath());
}

let projectRoot: string | null = null;
let termProc: ChildProcessWithoutNullStreams | null = null;
let termPty: pty.IPty | null = null;
let mainWindow: BrowserWindow | null = null;
let backendProc: ChildProcessWithoutNullStreams | null = null;
let backendStatus: "stopped" | "starting" | "healthy" | "error" = "stopped";
let backendError: string | null = null;
let backendPort: number | null = null;
let restartAttempts = 0;
let updateManager: UpdateManager | null = null;
let isQuitting = false;
// Guards against two concurrent restores (each performs a destructive data-dir
// swap — a second one racing the first would corrupt both).
let backupRestoreInProgress = false;

export function resolvePlatformDir(): string {
  if (process.env.AIC_PLATFORM_DIR && fs.existsSync(process.env.AIC_PLATFORM_DIR)) {
    return process.env.AIC_PLATFORM_DIR;
  }
  // Packaged: resources/backend (extraResources)
  if (process.resourcesPath) {
    const resourcesDir = path.join(process.resourcesPath, "backend");
    if (fs.existsSync(resourcesDir)) return resourcesDir;
  }
  // Dev: sibling of app/ (monorepo: AI-Company/backend)
  const appParentDir = path.join(app.getAppPath(), "..", "backend");
  if (fs.existsSync(appParentDir)) return appParentDir;
  const devWorkspace = path.join(__dirname, "..", "..", "..", "backend");
  if (fs.existsSync(devWorkspace)) return path.resolve(devWorkspace);
  return appParentDir;
}

/** Bundled portable Python (packaged) or local venv (dev). Never require system Python for production. */
export function resolvePythonPath(platformDir: string): string | null {
  const isWin = process.platform === "win32";
  const candidates: string[] = [];

  // 1) Packaged portable runtimes next to resources
  if (process.resourcesPath) {
    if (isWin) {
      candidates.push(path.join(process.resourcesPath, "python-win", "python.exe"));
    } else {
      candidates.push(path.join(process.resourcesPath, "python-linux", "bin", "python"));
      candidates.push(path.join(process.resourcesPath, "python-linux", "bin", "python3"));
    }
  }

  // 2) Dev packaging mirror (app/packaging/runtimes)
  const packagingRoot = path.join(app.getAppPath(), "..", "packaging", "runtimes");
  if (isWin) {
    candidates.push(path.join(packagingRoot, "python-win", "python.exe"));
  } else {
    candidates.push(path.join(packagingRoot, "python-linux", "bin", "python"));
    candidates.push(path.join(packagingRoot, "python-linux", "bin", "python3"));
  }

  // 3) Platform-local virtualenv (development)
  if (isWin) {
    candidates.push(path.join(platformDir, ".venv", "Scripts", "python.exe"));
    candidates.push(path.join(platformDir, "venv", "Scripts", "python.exe"));
  } else {
    candidates.push(path.join(platformDir, ".venv", "bin", "python"));
    candidates.push(path.join(platformDir, "venv", "bin", "python"));
  }

  // 4) Development-only system fallback (never preferred in packaged mode)
  if (!app.isPackaged) {
    if (!isWin) candidates.push("/usr/bin/python3");
    candidates.push(isWin ? "python.exe" : "python3");
    candidates.push("python");
  }

  for (const c of candidates) {
    if (!c) continue;
    // bare commands (dev fallback)
    if (!path.isAbsolute(c) && !c.includes(path.sep) && !c.includes("/") && !c.includes("\\")) {
      return c;
    }
    if (fs.existsSync(c)) return c;
  }
  return null;
}

async function checkBackendHealth(): Promise<boolean> {
  if (!backendPort) return false;
  try {
    const res = await fetch(`http://127.0.0.1:${backendPort}/health`);
    if (res.ok) {
      backendStatus = "healthy";
      backendError = null;
      return true;
    }
  } catch {
    // Not running yet
  }
  return false;
}

async function ensureBackendRunning(): Promise<void> {
  const isHealthy = await checkBackendHealth();
  if (isHealthy) {
    restartAttempts = 0;
    return;
  }

  backendStatus = "starting";
  const platformDir = resolvePlatformDir();
  const pythonPath = resolvePythonPath(platformDir);

  if (!pythonPath) {
    backendStatus = "error";
    backendError = app.isPackaged
      ? `Bundled Python runtime not found. Expected resources/python-${process.platform === "win32" ? "win" : "linux"}.`
      : `Python runtime not found for platform dir ${platformDir}`;
    return;
  }

  try {
    const logDir = path.join(appDataDir(), "logs");
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    const logFile = path.join(logDir, "backend-startup.log");
    const logStream = fs.createWriteStream(logFile, { flags: "w" });
    const logLine = (msg: string) => {
      const ts = new Date().toISOString();
      const line = `[${ts}] ${msg}\n`;
      logStream.write(line);
    };
    logLine(`=== AIC ADE Backend Startup ===`);
    logLine(`Platform: ${process.platform} ${process.arch}`);
    logLine(`Python: ${pythonPath}`);
    logLine(`CWD: ${platformDir}`);
    logLine(`AIC_DATA_DIR: ${appDataDir()}`);
    logLine(`PYTHONPATH: ${[platformDir, process.env.PYTHONPATH || ""].filter(Boolean).join(path.delimiter)}`);

    // H9: assign to the module-level backendPort so writeRuntimeState and the
    // health-check handlers see the same port (no local shadowing).
    backendPort = await findFreePort();
    logLine(`Backend port: ${backendPort}`);

    // Whitelist explicit env vars to prevent secret leakage
    const allowedEnvVars = new Set([
        'PYTHONPATH',
        'PYTHONUNBUFFERED', 
        'AIC_DATA_DIR',
        'AIC_IDENTITY_FILE',
        'AIC_JWT_SECRET',  // Required for JWT authentication
        'AIC_TESTING',
        'CI',
    ]);
    
    const filteredEnv: Record<string, string> = {};
    for (const [key, value] of Object.entries(process.env)) {
        if (allowedEnvVars.has(key) && value) {
            filteredEnv[key] = value;
        }
    }
    
    // CRITICAL: AIC_JWT_SECRET must be provided in production
    // Never auto-generate - requires explicit security configuration
    if (!process.env.AIC_JWT_SECRET) {
        throw new Error(
            "AIC_JWT_SECRET environment variable is required for production security.\n" +
            "Generate with: node -e \"console.log(require('crypto').randomBytes(32).toString('hex'))\"\n" +
            "Then set: export AIC_JWT_SECRET=<your_generated_secret>"
        );
    }
    const jwtSecret = process.env.AIC_JWT_SECRET!;  // Type assertion since we validated above
    
    backendProc = spawn(pythonPath, ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", String(backendPort)], {
      cwd: platformDir,
      env: {
        ...filteredEnv,
        PYTHONUNBUFFERED: "1",
        AIC_DATA_DIR: appDataDir(),
        AIC_IDENTITY_FILE: path.join(appDataDir(), "identity.json"),
        AIC_JWT_SECRET: jwtSecret,  // Required for backend JWT authentication  // Provide secret for production use
        PYTHONPATH: [platformDir, process.env.PYTHONPATH || ""].filter(Boolean).join(path.delimiter),
      },
      stdio: "pipe",
    });

    backendProc.stdout.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      logLine(`[stdout] ${text.trim()}`);
      if (text.includes("Uvicorn running on")) {
        backendStatus = "healthy";
        restartAttempts = 0;
        writeRuntimeState(backendPort, backendProc?.pid ?? null);
      }
    });

    backendProc.stderr.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      logLine(`[stderr] ${text.trim()}`);
      if (text.includes("Uvicorn running on")) {
        backendStatus = "healthy";
        restartAttempts = 0;
        writeRuntimeState(backendPort, backendProc?.pid ?? null);
      }
    });

    backendProc.on("error", (err: Error) => {
      backendStatus = "error";
      backendError = err.message;
      logLine(`[ERROR] Spawn failed: ${err.message}`);
      logStream.end();
    });

    backendProc.on("exit", (code: number | null) => {
      backendProc = null;
      // Drop the stale reference so quitAndInstall never kills a dead PID.
      updateManager?.setBackendProc(null);
      if (isQuitting) return;
      if (backendStatus !== "stopped") {
        backendStatus = "error";
        backendError = `Backend process exited with code ${code}`;
        logLine(`[EXIT] code=${code}`);
        logStream.end();
        // Auto-restart sidecar if crashed unexpectedly
        if (restartAttempts < 3) {
          restartAttempts++;
          setTimeout(() => {
            if (isQuitting) return;
            void ensureBackendRunning().then(() => {
              // Re-register the freshly spawned backend so quitAndInstall
              // targets the new PID, not the stale one.
              updateManager?.setBackendProc(backendProc);
            });
          }, 2000);
        }
      }
    });

    // Poll health for up to 15 seconds
    let becameHealthy = false;
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (await checkBackendHealth()) {
        restartAttempts = 0;
        becameHealthy = true;
        break;
      }
    }

    // M12: if the backend never became healthy within the poll window, surface
    // an error instead of hanging in "starting" forever. Kill the hung process
    // so it releases the port; the exit handler schedules the restart.
    if (!becameHealthy) {
      backendStatus = "error";
      backendError = "Backend did not become healthy within 15 seconds";
      logLine(`[ERROR] Backend health poll timed out (status=${backendStatus})`);
      if (backendProc) {
        backendProc.kill("SIGTERM");
      }
    }
  } catch (err: any) {
    backendStatus = "error";
    backendError = err?.message || String(err);
  }
}

// ── Backup / Restore helpers ─────────────────────────────────
const backupsDir = (): string => path.join(appDataDir(), "backups");

/** Wait for a spawned process to exit (bounded) so files it holds are released. */
function waitForExit(proc: ChildProcessWithoutNullStreams, timeoutMs = 10000): Promise<void> {
  return new Promise((resolve) => {
    if (proc.exitCode !== null) {
      resolve();
      return;
    }
    const timer = setTimeout(() => resolve(), timeoutMs);
    proc.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

/** Stop the backend sidecar and wait for it to release the data dir / DB. */
async function stopBackend(): Promise<void> {
  const proc = backendProc;
  if (proc) {
    // Mark stopped BEFORE killing so the exit handler never schedules a restart.
    backendStatus = "stopped";
    const exited = waitForExit(proc);
    proc.kill("SIGTERM");
    backendProc = null;
    await exited;
  } else {
    backendStatus = "stopped";
  }
  backendPort = null;
  try {
    fs.unlinkSync(path.join(appDataDir(), "runtime.json"));
  } catch {
    /* not present */
  }
}

/** POST to the running backend (backup endpoints). */
async function backendPost(pathname: string, body?: unknown): Promise<any> {
  if (!backendPort) throw new Error("Backend is not running");
  const res = await fetch(`http://127.0.0.1:${backendPort}${pathname}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errBody: any = await res.json();
      if (errBody?.detail) detail = String(errBody.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Extract a backup zip using the bundled Python stdlib — cross-platform and
 *  dependency-free for the packaged app (no third-party zip lib in deps).
 *  Runs with a zip-slip guard so archive entries cannot escape the target dir. */
async function extractBackupZip(zipPath: string, destDir: string): Promise<void> {
  const platformDir = resolvePlatformDir();
  const pythonPath = resolvePythonPath(platformDir);
  if (!pythonPath) throw new Error("Python runtime not found — cannot extract backup archive");
  const script = [
    "import sys, zipfile, pathlib",
    "src, dst = sys.argv[1], sys.argv[2]",
    "root = pathlib.Path(dst).resolve()",
    "with zipfile.ZipFile(src) as z:",
    "    for name in z.namelist():",
    "        target = (root / name).resolve()",
    "        if not (target == root or root in target.parents):",
    '            raise SystemExit("unsafe entry in archive: " + name)',
    "    z.extractall(dst)",
    "",
  ].join("\n");
  const scriptPath = path.join(app.getPath("temp"), `aic-extract-${Date.now()}.py`);
  fs.writeFileSync(scriptPath, script, "utf8");
  try {
    await new Promise<void>((resolve, reject) => {
      const proc = spawn(pythonPath, [scriptPath, zipPath, destDir], { stdio: "ignore" });
      proc.on("error", (err) => reject(err));
      proc.on("exit", (code) => {
        if (code === 0) resolve();
        else reject(new Error(`Backup extraction failed (python exited ${code})`));
      });
    });
  } finally {
    try {
      fs.unlinkSync(scriptPath);
    } catch {
      /* ignore */
    }
  }
}

/** If the archive wraps everything in a single top-level folder, unwrap it. */
function dataRootFromExtract(extractDir: string): string {
  const entries = fs.readdirSync(extractDir).filter((e) => e !== "__MACOSX" && !e.startsWith("."));
  if (entries.length === 1) {
    const only = path.join(extractDir, entries[0]);
    try {
      if (fs.statSync(only).isDirectory()) return only;
    } catch {
      /* fall through */
    }
  }
  return extractDir;
}

/** Verify the extracted data root has the backup manifest + snapshot DB. */
function verifyBackupContents(root: string): { ok: boolean; error?: string } {
  const manifestPath = path.join(root, "backup-manifest.json");
  if (!fs.existsSync(manifestPath)) {
    return { ok: false, error: "backup-manifest.json is missing from the archive" };
  }
  let manifest: Record<string, unknown> = {};
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  } catch {
    return { ok: false, error: "backup-manifest.json is not valid JSON" };
  }
  const dbCandidates = [manifest.db, manifest.database, manifest.snapshot_db, "aic.db", "snapshot.db", "data/aic.db"]
    .filter((c): c is string => typeof c === "string" && c.length > 0);
  const hasDb = dbCandidates.some((c) => fs.existsSync(path.join(root, c)));
  if (!hasDb) {
    return { ok: false, error: "snapshot database is missing from the archive" };
  }
  return { ok: true };
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    frame: false,
    backgroundColor: "#05060A",
    title: "AICompany ADE",
    icon: path.join(__dirname, process.platform === 'win32' ? '../../build/icon.ico' : '../../build/icon.png'),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // CSP: restrict resource loading to self + local engine only
  win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          isDev
            ? "default-src 'self' 'unsafe-inline' 'unsafe-eval' http://127.0.0.1:5174 ws://127.0.0.1:5174; object-src 'none'; frame-src 'none'; base-uri 'none'"
            : "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:*; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        ],
      },
    });
  });

  // Navigation guard — the preload bridge reaches host filesystem/terminal,
  // so remote pages must never be allowed to load inside this window.
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e, url) => {
    if (!isAllowedNavigation(url, path.resolve(app.getAppPath(), "dist"), isDev)) e.preventDefault();
  });
  win.webContents.on("will-redirect", (e, url) => {
    if (!isAllowedNavigation(url, path.resolve(app.getAppPath(), "dist"), isDev)) e.preventDefault();
  });

  mainWindow = win;
  win.once("ready-to-show", () => win.show());

  if (isDev) {
    win.loadURL("http://127.0.0.1:5174");
  } else {
    const indexHtml = path.join(__dirname, "..", "..", "dist", "index.html");
    win.loadFile(indexHtml);
  }

  win.on("closed", () => {
    if (termProc) {
      termProc.kill();
      termProc = null;
    }
    mainWindow = null;
  });

  return win;
}

function registerIpc(): void {
  ipcMain.handle("aic:get-identity", () => loadOrCreateIdentity());

  ipcMain.handle("aic:get-backend-status", async () => {
    await checkBackendHealth();
    return {
      status: backendStatus,
      error: backendError,
      logFile: path.join(appDataDir(), "logs", "backend-startup.log"),
      port: backendPort,
    };
  });

  ipcMain.handle("aic:store-get", (_e, key?: string) => {
    const store = readStore();
    if (!key) return store;
    return store[key];
  });

  ipcMain.handle("aic:store-set", (_e, key: string, value: unknown) => {
    const store = readStore();
    if (key === "projectRoot") {
      // projectRoot is the trust boundary for file access — never let the
      // renderer set an arbitrary path. Only validated non-sensitive paths
      // are accepted (native dialog / backend-selected projects).
      const safe = sanitizeProjectRoot(value, app.getPath("home"), app.getPath("temp"));
      if (value === null || value === undefined || value === "") {
        store.projectRoot = null;
        projectRoot = null;
        writeStore(store);
        return true;
      }
      if (safe === null) {
        throw new Error("projectRoot: invalid or unsafe path (must be an existing directory outside system roots)");
      }
      store.projectRoot = safe;
      projectRoot = safe;
      writeStore(store);
      return true;
    }
    store[key] = value;
    writeStore(store);
    return true;
  });

  ipcMain.handle("aic:open-path", async (_e, target: string) => {
    if (!target || typeof target !== "string") return { ok: false, error: "invalid path" };
    const safe = resolveSafe(target, projectRoot ? [projectRoot] : [], [appDataDir()]);
    const result = await shell.openPath(safe);
    return result ? { ok: false, error: result } : { ok: true };
  });

  ipcMain.handle("aic:open-external", async (_e, target: string) => {
    if (!target || typeof target !== "string" || !/^https:\/\/(github\.com|raw\.githubusercontent\.com|api\.github\.com)\//.test(target)) {
      return { ok: false, error: "external URL is not allowed" };
    }
    await shell.openExternal(target);
    return { ok: true };
  });

  ipcMain.handle("aic:select-directory", async () => {
    const res = await dialog.showOpenDialog({
      properties: ["openDirectory", "createDirectory"],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    projectRoot = res.filePaths[0];
    return projectRoot;
  });

  ipcMain.handle("aic:read-dir-tree", async (_e, dir: string, maxDepth = 4) => {
    if (!dir || typeof dir !== "string") throw new Error("invalid dir");
    const safe = resolveSafe(dir, projectRoot ? [projectRoot] : [], [appDataDir()]);

    async function build(basePath: string, depth: number): Promise<DirTreeNode[]> {
      if (depth <= 0) return [];
      const entries = await fs.promises.readdir(basePath, { withFileTypes: true });
      const filtered = entries
        .filter((e) => !e.name.startsWith(".") || e.name === ".env.example")
        .filter((e) => e.name !== "node_modules" && e.name !== "__pycache__")
        .sort((a, b) => {
          if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
          return a.name.localeCompare(b.name);
        });
      const result: DirTreeNode[] = [];
      for (const e of filtered) {
        const fullPath = path.join(basePath, e.name);
        const node: DirTreeNode = {
          name: e.name,
          path: fullPath,
          isDirectory: e.isDirectory(),
        };
        if (e.isDirectory()) {
          try {
            node.children = await build(fullPath, depth - 1);
          } catch {
            node.children = [];
          }
        }
        result.push(node);
      }
      return result;
    }

    return build(safe, maxDepth);
  });

  ipcMain.handle("aic:platform-mod", () =>
    process.platform === "darwin" ? "Meta" : "Control"
  );

  // PTY terminal — proper pseudo-terminal with colors, interactive programs
  // Validate CWD against symlinks and allowed roots (async/fs-promises version)
  async function validateCWD(cwdPath: string): Promise<string> {
    const fs = require('node:fs/promises');
    const path = require('node:path');
    
    const stat = await fs.stat(cwdPath);
    if (!stat.isDirectory()) throw new Error("Path is not a directory");
    
    // Recursively resolve symlinks asynchronously
    let resolvedPath = path.resolve(cwdPath);
    while (true) {
      try {
        const realPath = await fs.realpath(resolvedPath);
        if (realPath === resolvedPath) break;  // No more symlinks
        resolvedPath = realPath;
      } catch (e) {
        break;  // Stop at last resolvable point
      }
    }
    
    // Validate against allowed roots
    const allowedRoots = [projectRoot || appDataDir(), appDataDir()].filter(Boolean);
    if (allowedRoots.length === 0) throw new Error("No valid root configured");
    
    for (const root of allowedRoots) {
      if (resolvedPath.startsWith(root + path.sep)) return resolvedPath;
    }
    
    throw new Error("Path escapes allowed roots via symlink");
  }

  ipcMain.handle("aic:term-start", async (_e, cwd?: string) => {
    if (termPty) {
      termPty.kill();
      termPty = null;
    }
    if (termProc) {
      termProc.kill();
      termProc = null;
    }
    const root = cwd || projectRoot;
    if (!root) throw new Error("No project root — open a folder first");
    let safeCwd = root;
    try {
      safeCwd = await validateCWD(root);
    } catch (e: any) {
      throw new Error(`Invalid CWD: ${e.message}`);
    }
    const shellPath =
      process.platform === "win32"
        ? process.env.COMSPEC || "cmd.exe"
        : process.env.SHELL || "/bin/bash";
    const args = process.platform === "win32" ? [] : [];
    try {
      termPty = pty.spawn(shellPath, args, {
        name: "xterm-256color",
        cols: 80,
        rows: 24,
        cwd: safeCwd,
        env: { ...process.env, TERM: "xterm-256color" } as Record<string, string>,
      });
      termPty.onData((data) => {
        mainWindow?.webContents.send("aic:term-data", data);
      });
      termPty.onExit(({ exitCode }) => {
        mainWindow?.webContents.send("aic:term-data", `\n[shell exited ${exitCode}]\n`);
        termPty = null;
      });
      return { ok: true, shell: shellPath, cwd: safeCwd, pty: true };
    } catch {
      // Fallback to pipe if PTY unavailable
      const fallbackArgs = process.platform === "win32" ? [] : ["-i"];
      termProc = spawn(shellPath, fallbackArgs, {
        cwd: safeCwd,
        env: { ...process.env, TERM: "xterm-256color" },
        stdio: "pipe",
      });
      termProc.stdout.on("data", (buf: Buffer) => {
        mainWindow?.webContents.send("aic:term-data", buf.toString("utf8"));
      });
      termProc.stderr.on("data", (buf: Buffer) => {
        mainWindow?.webContents.send("aic:term-data", buf.toString("utf8"));
      });
      termProc.on("exit", (code) => {
        mainWindow?.webContents.send("aic:term-data", `\n[shell exited ${code}]\n`);
        termProc = null;
      });
      return { ok: true, shell: shellPath, cwd: safeCwd, pty: false };
    }
  });

  ipcMain.handle("aic:term-write", (_e, data: string) => {
    if (termPty) {
      termPty.write(data);
      return true;
    }
    if (termProc && termProc.stdin.writable) {
      termProc.stdin.write(data);
      return true;
    }
    return false;
  });

  ipcMain.handle("aic:term-kill", () => {
    if (termPty) {
      termPty.kill();
      termPty = null;
    }
    if (termProc) {
      termProc.kill();
      termProc = null;
    }
    return true;
  });

  // ── Auto Update ──────────────────────────────────────
  ipcMain.handle("aic:update-get-state", () => updateManager?.getState() ?? null);
  ipcMain.handle("aic:update-check", async () => {
    if (!updateManager) return null;
    return updateManager.checkForUpdates();
  });
  ipcMain.handle("aic:update-download", async () => {
    if (!updateManager) return null;
    return updateManager.downloadUpdate();
  });
  ipcMain.handle("aic:update-install", async () => {
    if (!updateManager) return null;
    return updateManager.installUpdate();
  });
  ipcMain.handle("aic:update-quit-and-install", () => {
    updateManager?.quitAndInstall();
    return true;
  });
  ipcMain.handle("aic:update-dismiss", () => {
    updateManager?.dismiss();
    return updateManager?.getState() ?? null;
  });
  ipcMain.handle("aic:get-app-version", () => app.getVersion());

  // ── Backup / Restore ────────────────────────────────────
  ipcMain.handle("aic:backup-create-to", async (_e, filename?: string): Promise<{
    saved: boolean;
    path?: string;
    error?: string;
    cancelled?: boolean;
  }> => {
    try {
      // The renderer usually creates the archive via POST /backup/create and
      // passes the filename; if it didn't (or the name is unsafe), create it
      // here so the save dialog always has a real file to copy.
      await ensureBackendRunning();
      let backupFilename = typeof filename === "string" ? path.basename(filename) : "";
      if (!backupFilename || !backupFilename.toLowerCase().endsWith(".zip")) {
        // QA-AUTH: this fallback runs in the main process, which has no access to
        // the renderer's per-install Bearer token. The renderer normally creates
        // the archive via the token-carrying apiClient (backupApi.createBackup)
        // and passes the filename here, so this branch is only reached when that
        // didn't happen. If auth is enforced, surface a clear error instead of a
        // bare 401.
        let created: any;
        try {
          created = await backendPost("/backup/create");
        } catch (e: any) {
          const detail: string = e?.message || String(e);
          if (/401|403|unauthori[sz]ed|not.?authenticated/i.test(detail)) {
            return { saved: false, error: "Backup requires the app token. Create the backup from the app's Backup panel." };
          }
          throw e;
        }
        backupFilename = typeof created?.filename === "string" ? path.basename(created.filename) : "";
      }
      if (!backupFilename || !backupFilename.toLowerCase().endsWith(".zip")) {
        return { saved: false, error: "Backend returned an invalid backup filename" };
      }
      const srcFile = path.join(backupsDir(), backupFilename);
      if (!fs.existsSync(srcFile)) {
        return { saved: false, error: `Backup file not found on disk: ${backupFilename}` };
      }
      const opts = {
        title: "Save Backup",
        defaultPath: backupFilename,
        filters: [{ name: "Backup Archive", extensions: ["zip"] }],
      };
      const res = mainWindow
        ? await dialog.showSaveDialog(mainWindow, opts)
        : await dialog.showSaveDialog(opts);
      if (res.canceled || !res.filePath) return { saved: false, cancelled: true };
      fs.copyFileSync(srcFile, res.filePath);
      return { saved: true, path: res.filePath };
    } catch (e: any) {
      return { saved: false, error: e?.message || String(e) };
    }
  });

  ipcMain.handle("aic:backup-restore", async (): Promise<{
    restored: boolean;
    error?: string;
    rollbackDone?: boolean;
  }> => {
    let releaseBackupLock = async () => {};
    try {
        releaseBackupLock = await acquireBackupLock();
    } catch (e) {
        return { restored: false, error: "Failed to acquire lock" };
    }
    
    let tmpRoot: string | null = null;
    let preRestoreDir: string | null = null;
    try {
      const openOpts = {
        title: "Restore from Backup",
        properties: ["openFile"] as Array<"openFile">,
        filters: [{ name: "Backup Archive", extensions: ["zip"] }],
      };
      const res = mainWindow
        ? await dialog.showOpenDialog(mainWindow, openOpts)
        : await dialog.showOpenDialog(openOpts);
      if (res.canceled || !res.filePaths[0]) return { restored: false, error: "cancelled" };
      const zipPath = res.filePaths[0];
      if (!fs.existsSync(zipPath)) return { restored: false, error: "Selected file does not exist" };

      // Extract to a sibling of the data dir (same filesystem → atomic renames).
      tmpRoot = fs.mkdtempSync(path.join(app.getPath("userData"), "aic-restore-"));
      await extractBackupZip(zipPath, tmpRoot);
      const dataRoot = dataRootFromExtract(tmpRoot);
      const check = verifyBackupContents(dataRoot);
      if (!check.ok) throw new Error(check.error || "Invalid backup archive");

      // Stop the backend before touching its DB/files.
      await stopBackend();

      // Safety copy of the current data for rollback.
      const ts = Date.now();
      preRestoreDir = `${appDataDir()}.pre-restore-${ts}`;
      fs.renameSync(appDataDir(), preRestoreDir);

      fs.mkdirSync(appDataDir(), { recursive: true });
      for (const entry of fs.readdirSync(dataRoot)) {
        fs.renameSync(path.join(dataRoot, entry), path.join(appDataDir(), entry));
      }
      // runtime.json is transient — the freshly spawned backend rewrites it.
      try {
        fs.unlinkSync(path.join(appDataDir(), "runtime.json"));
      } catch {
        /* ignore */
      }
      // Keep the desktop credential stable across machines/installs.
      const identityPath = path.join(preRestoreDir, "identity.json");
      if (fs.existsSync(identityPath)) {
        fs.copyFileSync(identityPath, path.join(appDataDir(), "identity.json"));
      }

      await ensureBackendRunning();
      updateManager?.setBackendProc(backendProc);
      return { restored: true };
    } catch (e: any) {
      let rollbackDone = false;
      if (preRestoreDir && fs.existsSync(preRestoreDir)) {
        try {
          fs.rmSync(appDataDir(), { recursive: true, force: true });
          fs.renameSync(preRestoreDir, appDataDir());
          rollbackDone = true;
        } catch (rbErr) {
          console.error("[backup-restore] rollback failed", rbErr);
        }
      }
      try {
        await ensureBackendRunning();
        updateManager?.setBackendProc(backendProc);
      } catch (restartErr) {
        console.error("[backup-restore] backend restart after failure failed", restartErr);
      }
      return { restored: false, error: e?.message || String(e), rollbackDone };
    } finally {
      await releaseBackupLock();
      try {
        if (tmpRoot) fs.rmSync(tmpRoot, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
    }
  });

  // Window controls
  // Cleanup terminal when window closes (prevent hangs)
  mainWindow?.webContents.on('destroyed', () => {
    termPty?.kill();
    termProc?.kill();
    termPty = null;
    termProc = null;
  });
  

  ipcMain.handle("aic:minimize", () => {
    mainWindow?.minimize();
    return true;
  });
  ipcMain.handle("aic:maximize", () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
    return true;
  });
  ipcMain.handle("aic:close", () => {
    mainWindow?.close();
    return true;
  });
}

function initUpdateManager(): void {
  const store = readStore();
  const saved = (store.updateConfig && typeof store.updateConfig === "object"
    ? store.updateConfig
    : {}) as Partial<UpdateConfig>;
  let baseUrl: string;
  try {
    baseUrl = resolveUpdateBaseUrl(
      typeof saved.baseUrl === "string" ? saved.baseUrl : null,
      process.env as Record<string, string | undefined>
    );
  } catch {
    // Invalid persisted base URL — fall back to the default rather than crash.
    baseUrl = DEFAULT_UPDATE_BASE_URL;
  }
  updateManager = new UpdateManager(
    defaultUpdateConfig({
      ...saved,
      baseUrl,
    })
  );
  updateManager.on((state) => {
    mainWindow?.webContents.send("aic:update-state-changed", state);
  });
  // Background check — never block startup
  if (updateManager.getConfig().autoCheck) {
    setTimeout(() => {
      void updateManager?.checkForUpdates({ silent: true });
    }, 12000);
  }
}

// ── Global crash handling ──────────────────────────────────────
process.on("uncaughtException", (err) => {
  console.error("[uncaughtException]", err);
  try {
    dialog.showErrorBox("AIC ADE — Unexpected Error", (err?.stack as string) || String(err));
  } catch { /* ignore */ }
});
process.on("unhandledRejection", (reason) => {
  console.error("[unhandledRejection]", reason);
});
app.on("render-process-gone", (_e, _wc, details) => {
  console.error("[render-process-gone]", details);
  try {
    dialog.showErrorBox("AIC ADE — Renderer crashed", `Reason: ${details.reason}`);
  } catch { /* ignore */ }
});

// ── Single instance lock ───────────────────────────────────────
// Two instances would both spawn sidecars and fight over runtime.json /
// SQLite. Second instance focuses the existing window instead.
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    nativeTheme.themeSource = "dark";
    ensureAppData();
    // Generate/persist the per-install identity before the backend spawns so
    // AIC_IDENTITY_FILE always points at an existing file.
    loadOrCreateIdentity();
    const store = readStore();
    if (typeof store.projectRoot === "string") projectRoot = store.projectRoot;
    initUpdateManager();
    registerIpc();
    // Show the window immediately — never block startup on the backend.
    createWindow();
    // Start the backend sidecar in the background.
    void ensureBackendRunning().then(() => {
      updateManager?.setBackendProc(backendProc);
    });
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
        // The backend stays alive on macOS; restart it only if it is not running.
        if (backendStatus === "stopped" || backendStatus === "error") {
          void ensureBackendRunning();
        }
      }
    });
  });
}

app.on("will-quit", () => {
  isQuitting = true;
  backendStatus = "stopped";
  if (backendProc) {
    backendProc.kill("SIGTERM");
    backendProc = null;
  }
});

app.on("window-all-closed", () => {
  if (termPty) termPty.kill();
  if (termProc) termProc.kill();
  if (process.platform !== "darwin") {
    // Mark the backend as stopped BEFORE killing so the exit handler never
    // schedules a restart while we are tearing down.
    backendStatus = "stopped";
    if (backendProc) {
      backendProc.kill("SIGTERM");
      backendProc = null;
    }
    app.quit();
  }
  // macOS: keep the app and backend alive so `activate` can recreate the
  // window immediately. Do NOT kill the sidecar here.
});
