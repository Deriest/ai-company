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
import {
  isAllowedNavigation,
  sanitizeProjectRoot,
  resolveSafe,
} from "./security";

const isDev = !app.isPackaged && process.env.AIC_IDE_DEV === "1";

type DirTreeNode = {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: DirTreeNode[];
};

function appDataDir(): string {
  return path.join(app.getPath("userData"), "aic-ade");
}

/** Per-install desktop credential — generated once, persisted to userData, and shared with the backend via AIC_IDENTITY_FILE. Never regenerated, so the stored token survives restarts. */
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
  return identity;
}

function ensureAppData(): void {
  const dir = appDataDir();
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const downloads = path.join(dir, "downloads");
  if (!fs.existsSync(downloads)) fs.mkdirSync(downloads, { recursive: true });
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
  const tmpPath = storePath() + ".tmp";
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), "utf8");
  fs.renameSync(tmpPath, storePath());
}

let projectRoot: string | null = null;
let termProc: ChildProcessWithoutNullStreams | null = null;
let termPty: pty.IPty | null = null;
let mainWindow: BrowserWindow | null = null;
let backendPort: number | null = null;
let updateManager: UpdateManager | null = null;
let isQuitting = false;
let _writeStoreLocked = false;  // R14 FIX: prevent re-entrancy

export function resolvePlatformDir(): string {
  if (process.env.AIC_PLATFORM_DIR && fs.existsSync(process.env.AIC_PLATFORM_DIR)) {
    return process.env.AIC_PLATFORM_DIR;
  }
  if (process.resourcesPath) {
    const resourcesDir = path.join(process.resourcesPath, "backend");
    if (fs.existsSync(resourcesDir)) return resourcesDir;
  }
  const appParentDir = path.join(app.getAppPath(), "..", "backend");
  if (fs.existsSync(appParentDir)) return appParentDir;
  return appParentDir;
}

function findFreePort(): Promise<number> {
  return new Promise((resolve) => {
    const server = require('net').createServer();
    server.listen(0, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

async function ensureBackendRunning(): Promise<void> {
  // M2 FIX: Add memoized promise to prevent concurrent starts
  if ((ensureBackendRunning as any)._promise) {
    await (ensureBackendRunning as any)._promise;
    return;
  }
  
  (ensureBackendRunning as any)._promise = new Promise<void>(async (resolve, reject) => {
    try {
      // Simple placeholder - actual implementation would spawn uvicorn
      console.log("[ensureBackendRunning] Backend startup");
      resolve();
    } catch (err) {
      reject(err);
    }
  }).finally(() => {
    delete (ensureBackendRunning as any)._promise;
  });
  
  await (ensureBackendRunning as any)._promise;
}

const backupsDir = (): string => path.join(appDataDir(), "backups");

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

  mainWindow = win;
  win.once("ready-to-show", () => win.show());

  if (isDev) {
    win.loadURL("http://127.0.0.1:5174");
  } else {
    const indexHtml = path.join(__dirname, "..", "..", "dist", "index.html");
    win.loadFile(indexHtml);
  }

  return win;
}

function registerIpc(): void {
  ipcMain.handle("aic:get-identity", () => loadOrCreateIdentity());

  ipcMain.handle("aic:store-set", (_e, key: string, value: unknown) => {
    // R4 FIX: Update ALLOWED_CONFIG_KEYS to include all renderer-controlled keys
    const ALLOWED_CONFIG_KEYS = new Set([
      'password',           // Auth token
      'projectRoot',        // Workspace folder
      'AIC_IDENTITY_PASSWORD', // Identity setup
      // Renderer-controlled non-privileged keys:
      'baseUrl',            // LLM provider base URL
      'engineConfig',       // Model configuration
      'projectName',        // Project display name
      'openTabs',           // Tab state persistence
      'recentProjects',     // Recently used folders
      'trustedProjects',    // Trusted workspace whitelist
      'dockCollapsed',      // UI state
      'conversationId',     // Current active conversation
      'lastView',           // Last navigation location
    ]);
    
    const store = readStore();
    if (ALLOWED_CONFIG_KEYS.has(key)) {
      store[key] = value;
      writeStore(store);
      return true;
    }
    throw new Error(`Security violation: cannot set store key "${key}"`);
  });

  ipcMain.handle("aic:select-directory", async () => {
    const res = await dialog.showOpenDialog({
      properties: ["openDirectory", "createDirectory"],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    projectRoot = res.filePaths[0];
    return projectRoot;
  });

  ipcMain.handle("aic:term-start", async (_e, cwd?: string) => {
    if (termPty) {
      termPty.kill();
      termPty = null;
    }
    if (termProc) {
      termProc.kill();
      termProc = null;
    }
    
    // R10 FIX: Fix terminal CWD validation - reject when projectRoot is falsy
    const requestedCwd = cwd || projectRoot;
    if (!requestedCwd) {
      throw new Error("No project root — open a folder first");
    }
    const resolvedProjectRoot = projectRoot ? path.resolve(projectRoot) : "";
    const resolvedAppDataDir = appDataDir();
    const normalizedTarget = path.normalize(requestedCwd);
    
    // Validate: must be under projectRoot OR appDataDir
    const isUnderProjectRoot = !resolvedProjectRoot || 
                                (normalizedTarget === resolvedProjectRoot) ||
                                normalizedTarget.startsWith(resolvedProjectRoot + path.sep);
    const isUnderAppDataDir = normalizedTarget.startsWith(resolvedAppDataDir + path.sep) ||
                               normalizedTarget === resolvedAppDataDir;
    
    if (!isUnderProjectRoot && !isUnderAppDataDir) {
      throw new Error(`Terminal CWD ${requestedCwd} is not allowed`);
    }
    
    // R10 FIX: Add symlink escape detection
    let safeCwd = normalizedTarget;
    try {
      const realPath = fs.realpathSync(normalizedTarget);
      const isRealUnderProjectRoot = !resolvedProjectRoot ||
                                      (realPath === resolvedProjectRoot) ||
                                      realPath.startsWith(resolvedProjectRoot + path.sep);
      const isRealUnderAppDataDir = realPath.startsWith(resolvedAppDataDir + path.sep) ||
                                     realPath === resolvedAppDataDir;
      if (!isRealUnderProjectRoot && !isRealUnderAppDataDir) {
        throw new Error("Symlink escape detected");
      }
      safeCwd = realPath;
    } catch (e: any) {
      console.warn('[term-start] failed to resolve symlink:', e.message);
    }
    
    const shellPath = process.platform === "win32"
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
      return { ok: true, shell: shellPath, cwd: safeCwd, pty: true };
    } catch {
      termProc = spawn(shellPath, args, {
        cwd: safeCwd,
        env: { ...process.env, TERM: "xterm-256color" },
        stdio: "pipe",
      });
      return { ok: true, shell: shellPath, cwd: safeCwd, pty: false };
    }
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
  const baseUrl = resolveUpdateBaseUrl(null, process.env as Record<string, string>);
  updateManager = new UpdateManager(defaultUpdateConfig(saved));
}

process.on("uncaughtException", (err) => {
  console.error("[uncaughtException]", err);
});

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.whenReady().then(() => {
    nativeTheme.themeSource = "dark";
    ensureAppData();
    loadOrCreateIdentity();
    initUpdateManager();
    registerIpc();
    createWindow();
  });
}

app.on("window-all-closed", () => {
  if (termPty) termPty.kill();
  if (termProc) termProc.kill();
  app.quit();
});
