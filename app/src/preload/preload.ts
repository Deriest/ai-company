import { contextBridge, ipcRenderer } from "electron";

export type DirTreeNode = {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: DirTreeNode[];
};

export type UpdateStateDto = {
  status: string;
  currentVersion: string;
  availableVersion?: string;
  releaseNotes?: string;
  mandatory?: boolean;
  progress?: number;
  bytesDownloaded?: number;
  bytesTotal?: number;
  speedBps?: number;
  error?: string;
  downloadPath?: string;
  lastCheckedAt?: string | null;
  baseUrl: string;
  channel: string;
  dismissedVersion?: string;
};

const api = {
  getBackendStatus: (): Promise<{
    status: "stopped" | "starting" | "healthy" | "error";
    error?: string | null;
    port: number;
    logFile?: string;
  }> => ipcRenderer.invoke("aic:get-backend-status"),
  getIdentity: (): Promise<{ username: string; password: string }> =>
    ipcRenderer.invoke("aic:get-identity"),
  storeGet: (key?: string): Promise<unknown> => ipcRenderer.invoke("aic:store-get", key),
  storeSet: (key: string, value: unknown): Promise<boolean> =>
    ipcRenderer.invoke("aic:store-set", key, value),
  openPath: (target: string): Promise<{ ok: boolean; error?: string }> =>
    ipcRenderer.invoke("aic:open-path", target),
  openExternal: (target: string): Promise<{ ok: boolean; error?: string }> =>
    ipcRenderer.invoke("aic:open-external", target),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("aic:select-directory"),
  readDirTree: (dir: string, maxDepth?: number): Promise<DirTreeNode[]> =>
    ipcRenderer.invoke("aic:read-dir-tree", dir, maxDepth),
  platformMod: (): Promise<string> => ipcRenderer.invoke("aic:platform-mod"),
  termStart: (cwd?: string): Promise<{ ok: boolean; shell: string; cwd: string }> =>
    ipcRenderer.invoke("aic:term-start", cwd),
  termWrite: (data: string): Promise<boolean> => ipcRenderer.invoke("aic:term-write", data),
  termKill: (): Promise<boolean> => ipcRenderer.invoke("aic:term-kill"),
  onTermData: (cb: (data: string) => void): (() => void) => {
    const handler = (_: unknown, data: string) => cb(data);
    ipcRenderer.on("aic:term-data", handler);
    return () => ipcRenderer.removeListener("aic:term-data", handler);
  },

  // Auto Update
  getAppVersion: (): Promise<string> => ipcRenderer.invoke("aic:get-app-version"),
  updateGetState: (): Promise<UpdateStateDto | null> => ipcRenderer.invoke("aic:update-get-state"),
  updateCheck: (): Promise<void> => ipcRenderer.invoke("aic:update-check"),
  updateDownload: (): Promise<void> => ipcRenderer.invoke("aic:update-download"),
  updateInstall: (): Promise<void> => ipcRenderer.invoke("aic:update-install"),
  updateQuitAndInstall: (): Promise<void> => ipcRenderer.invoke("aic:update-quit-and-install"),
  updateDismiss: (): Promise<void> => ipcRenderer.invoke("aic:update-dismiss"),

  // Window controls
  minimize: (): Promise<boolean> => ipcRenderer.invoke("aic:minimize"),
  maximize: (): Promise<boolean> => ipcRenderer.invoke("aic:maximize"),
  close: (): Promise<boolean> => ipcRenderer.invoke("aic:close"),

  // Backup / Restore
  backupCreateTo: (filename?: string): Promise<{
    saved: boolean;
    path?: string;
    error?: string;
    cancelled?: boolean;
  }> => ipcRenderer.invoke("aic:backup-create-to", filename),
  backupRestore: (): Promise<{
    restored: boolean;
    error?: string;
    rollbackDone?: boolean;
  }> => ipcRenderer.invoke("aic:backup-restore"),

  onUpdateStateChanged: (cb: (state: UpdateStateDto) => void) => {
    const handler = (_e: any, s: UpdateStateDto) => cb(s);
    ipcRenderer.on("aic:update-state-changed", handler);
    return () => {
      ipcRenderer.off("aic:update-state-changed", handler);
    };
  },
};

contextBridge.exposeInMainWorld("aic", api);
export type AicBridge = typeof api;
