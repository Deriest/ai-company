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
import os from "node:os";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import net from "node:net";
import * as pty from "node-pty";
import { UpdateManager } from "./updateManager";
import {
  defaultUpdateConfig,
  resolveUpdateBaseUrl,
  DEFAULT_UPDATE_BASE_URL,
  type UpdateConfig,
} from "./updateConfig";

const isDev = !app.isPackaged && process.env.AIC_IDE_DEV === "1";

type DirTreeNode = {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: DirTreeNode[];
};

/** Allowed roots for read/write — app data dir only (covers store, downloads, logs, staged updates).
 *  Project folders are attached per-call via `resolveSafe(..., [projectRoot])`.
 *  Home / Documents / Temp are intentionally NOT included (world-writable or sensitive). */
function allowedRoots(): string[] {
  return [appDataDir()];
}

/** Reject project-root values that would expand the renderer's file access to the whole machine. */
const SENSITIVE_FS_ROOTS = new Set([
  "/", "/home", "/root", "/etc", "/usr", "/var", "/tmp", "/bin", "/sbin",
  "/lib", "/lib64", "/proc", "/sys", "/dev", "/boot", "/opt", "/mnt",
  "/media", "/run", "/srv", "/snap", "/nix", "/Volumes", "/System",
  "/Library", "/Private", "/Users", "/Applications", "/Windows",
  "/Program Files", "/Program Files (x86)", "C:\\", "C:\\Windows",
  "C:\\Program Files", "C:\\Program Files (x86)", "C:\\Users",
]);

function sanitizeProjectRoot(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") return null;
  let resolved: string;
  try {
    resolved = path.resolve(value);
  } catch {
    return null;
  }
  const lower = resolved.toLowerCase();
  if (SENSITIVE_FS_ROOTS.has(resolved) || SENSITIVE_FS_ROOTS.has(lower)) return null;
  const home = path.resolve(app.getPath("home"));
  if (resolved === home || resolved === path.resolve(app.getPath("temp"))) return null;
  // Must be an existing directory.
  try {
    const st = fs.statSync(resolved);
    if (!st.isDirectory()) return null;
  } catch {
    return null;
  }
  return resolved;
}

function resolveSafe(target: string, extraRoots: string[] = []): string {
  const resolved = path.resolve(target);
  const roots = [...allowedRoots(), ...extraRoots].map((r) => path.resolve(r));
  const ok = roots.some((root) => resolved === root || resolved.startsWith(root + path.sep));
  if (!ok) throw new Error(`path not allowed: ${resolved}`);
  // block symlink escape: lstat the resolved path, reject if symlink pointing outside roots
  try {
    const real = fs.realpathSync(resolved);
    if (real !== resolved) {
      const realOk = roots.some((root) => real === root || real.startsWith(root + path.sep));
      if (!realOk) throw new Error(`symlink escape blocked: ${resolved} → ${real}`);
    }
  } catch (e) {
    // path may not exist yet (write case) — only block if it exists and is a symlink
    if (fs.existsSync(resolved)) throw e;
  }
  return resolved;
}

function appDataDir(): string {
  return path.join(app.getPath("userData"), "aic-ade");
}

function ensureAppData(): void {
  const dir = appDataDir();
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const downloads = path.join(dir, "downloads");
  if (!fs.existsSync(downloads)) fs.mkdirSync(downloads, { recursive: true });
  // Scrub legacy web-era secrets from persisted store
  try {
    const store = readStore();
    if ("password" in store) {
      delete store.password;
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
  fs.writeFileSync(storePath(), JSON.stringify(data, null, 2), "utf8");
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

/** Find a free TCP port — try from start until one is available. */
export function findFreePort(start: number = 8000, end: number = 8099, host: string = "127.0.0.1"): Promise<number> {
  return new Promise((resolve, reject) => {
    let port = start;
    const tryNext = (): void => {
      if (port > end) {
        reject(new Error(`No free ports in range ${start}-${end}`));
        return;
      }
      const socket = net.createConnection({ host, port });
      socket.setTimeout(300);
      socket.on("connect", () => {
        socket.destroy();
        port++;
        tryNext();
      });
      socket.on("error", () => {
        socket.destroy();
        resolve(port);
      });
      socket.on("timeout", () => {
        socket.destroy();
        resolve(port);
      });
    };
    tryNext();
  });
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

    const backendPort = await findFreePort();
    logLine(`Backend port: ${backendPort}`);

    backendProc = spawn(pythonPath, ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", String(backendPort)], {
      cwd: platformDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        AIC_DATA_DIR: appDataDir(),
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
            void ensureBackendRunning();
          }, 2000);
        }
      }
    });

    // Poll health for up to 15 seconds
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (await checkBackendHealth()) {
        restartAttempts = 0;
        break;
      }
    }
  } catch (err: any) {
    backendStatus = "error";
    backendError = err?.message || String(err);
  }
}

/** Navigation allowlist — only the app's own file:// pages and (in dev) the Vite server. */
function isAllowedNavigation(url: string): boolean {
  try {
    const u = new URL(url);
    if (u.protocol === "file:") return true;
    if (isDev && u.protocol === "http:" && u.hostname === "127.0.0.1" && u.port === "5174") return true;
    return false;
  } catch {
    return false;
  }
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
            : "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:*; object-src 'none'; frame-src 'none'; base-uri 'none'",
        ],
      },
    });
  });

  // Navigation guard — the preload bridge reaches host filesystem/terminal,
  // so remote pages must never be allowed to load inside this window.
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e, url) => {
    if (!isAllowedNavigation(url)) e.preventDefault();
  });
  win.webContents.on("will-redirect", (e, url) => {
    if (!isAllowedNavigation(url)) e.preventDefault();
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
  ipcMain.handle("aic:get-backend-status", async () => {
    await checkBackendHealth();
    return {
      status: backendStatus,
      error: backendError,
      logFile: path.join(appDataDir(), "logs", "backend-startup.log"),
      port: backendPort,
    };
  });

  ipcMain.handle("aic:get-paths", () => ({
    home: app.getPath("home"),
    userData: appDataDir(),
    documents: app.getPath("documents"),
    temp: app.getPath("temp"),
    downloads: path.join(appDataDir(), "downloads"),
    platform: process.platform,
    arch: process.arch,
    hostname: os.hostname(),
  }));

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
      const safe = sanitizeProjectRoot(value);
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
    const safe = resolveSafe(target, projectRoot ? [projectRoot] : []);
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

  ipcMain.handle("aic:show-item", (_e, target: string) => {
    if (!target || typeof target !== "string") return false;
    const safe = resolveSafe(target, projectRoot ? [projectRoot] : []);
    shell.showItemInFolder(safe);
    return true;
  });

  ipcMain.handle("aic:select-directory", async () => {
    const res = await dialog.showOpenDialog({
      properties: ["openDirectory", "createDirectory"],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    projectRoot = res.filePaths[0];
    return projectRoot;
  });

  ipcMain.handle("aic:select-file", async () => {
    const res = await dialog.showOpenDialog({
      properties: ["openFile"],
      defaultPath: projectRoot || undefined,
    });
    if (res.canceled || !res.filePaths[0]) return null;
    return res.filePaths[0];
  });

  ipcMain.handle("aic:read-dir", async (_e, dir: string) => {
    if (!dir || typeof dir !== "string") throw new Error("invalid dir");
    const safe = resolveSafe(dir, projectRoot ? [projectRoot] : []);
    const entries = await fs.promises.readdir(safe, { withFileTypes: true });
    return entries
      .filter((e) => !e.name.startsWith(".") || e.name === ".env.example")
      .map((e) => ({
        name: e.name,
        isDirectory: e.isDirectory(),
        path: path.join(safe, e.name),
      }));
  });

  ipcMain.handle("aic:read-dir-tree", async (_e, dir: string, maxDepth = 4) => {
    if (!dir || typeof dir !== "string") throw new Error("invalid dir");
    const safe = resolveSafe(dir, projectRoot ? [projectRoot] : []);

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

  ipcMain.handle("aic:read-file", async (_e, filePath: string) => {
    if (!filePath || typeof filePath !== "string") throw new Error("invalid path");
    const safe = resolveSafe(filePath, projectRoot ? [projectRoot] : []);
    const stat = await fs.promises.stat(safe);
    if (stat.size > 2_000_000) throw new Error("file too large (>2MB)");
    const buf = await fs.promises.readFile(safe);
    return buf.toString("utf8");
  });

  ipcMain.handle("aic:write-file", async (_e, filePath: string, content: string) => {
    if (!filePath || typeof filePath !== "string") throw new Error("invalid path");
    const safe = resolveSafe(filePath, projectRoot ? [projectRoot] : []);
    await fs.promises.writeFile(safe, content, "utf8");
    return true;
  });

  ipcMain.handle("aic:create-file", async (_e, filePath: string) => {
    if (!filePath || typeof filePath !== "string") throw new Error("invalid path");
    const safe = resolveSafe(filePath, projectRoot ? [projectRoot] : []);
    if (fs.existsSync(safe)) throw new Error("file already exists");
    await fs.promises.writeFile(safe, "", "utf8");
    return true;
  });

  ipcMain.handle("aic:delete-file", async (_e, filePath: string) => {
    if (!filePath || typeof filePath !== "string") throw new Error("invalid path");
    const safe = resolveSafe(filePath, projectRoot ? [projectRoot] : []);
    const stat = await fs.promises.lstat(safe);
    if (stat.isDirectory()) await fs.promises.rmdir(safe, { recursive: true });
    else await fs.promises.unlink(safe);
    return true;
  });

  ipcMain.handle("aic:rename-file", async (_e, oldPath: string, newName: string) => {
    if (!oldPath || !newName) throw new Error("invalid args");
    const safeOld = resolveSafe(oldPath, projectRoot ? [projectRoot] : []);
    const dir = path.dirname(safeOld);
    const safeNew = resolveSafe(path.join(dir, newName), projectRoot ? [projectRoot] : []);
    await fs.promises.rename(safeOld, safeNew);
    return safeNew;
  });

  ipcMain.handle("aic:save-blob", async (_e, filename: string, data: ArrayBuffer) => {
    ensureAppData();
    const safeName = path.basename(filename).replace(/[^\w.\-]+/g, "_");
    const dest = path.join(appDataDir(), "downloads", safeName);
    const buf = Buffer.from(data);
    if (buf.length > 100_000_000) throw new Error("blob too large (>100MB)");
    await fs.promises.writeFile(dest, buf);
    return dest;
  });

  ipcMain.handle("aic:platform-mod", () =>
    process.platform === "darwin" ? "Meta" : "Control"
  );

  // PTY terminal — proper pseudo-terminal with colors, interactive programs
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
    const safeCwd = resolveSafe(root, [root]);
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

  ipcMain.handle("aic:term-resize", (_e, cols: number, rows: number) => {
    if (termPty) {
      termPty.resize(cols, rows);
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
  ipcMain.handle("aic:update-get-config", () => updateManager?.getConfig() ?? null);
  ipcMain.handle("aic:update-set-config", (_e, partial: Partial<UpdateConfig>) => {
    if (!updateManager) return null;
    const cfg = updateManager.getConfig();
    const next = { ...cfg, ...(partial || {}) };
    if (typeof next.baseUrl === "string") {
      // Validate via resolveUpdateBaseUrl (requires https:// or http://127.0.0.1); throws on invalid.
      const resolved = resolveUpdateBaseUrl(next.baseUrl, process.env as Record<string, string | undefined>);
      next.baseUrl = resolved;
    }
    updateManager.setConfig(next);
    const store = readStore();
    const saved = updateManager.getConfig();
    store.updateConfig = saved;
    writeStore(store);
    return saved;
  });
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

  // Window controls
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
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
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
  // Mark the backend as stopped BEFORE killing so the exit handler never
  // schedules a restart while we are tearing down.
  backendStatus = "stopped";
  if (backendProc) {
    backendProc.kill("SIGTERM");
    backendProc = null;
  }
  if (process.platform !== "darwin") app.quit();
});
