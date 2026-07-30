import { contextBridge, ipcRenderer } from "electron";

export type AicPaths = {
  home: string;
  userData: string;
  documents: string;
  temp: string;
  downloads?: string;
  platform: NodeJS.Platform;
  arch: string;
  hostname: string;
};

export type DirEntry = {
  name: string;
  isDirectory: boolean;
  path: string;
};

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

export type UpdateConfigDto = {
  baseUrl: string;
  channel: string;
  autoCheck: boolean;
  autoDownload: boolean;
  notifyBeforeInstall: boolean;
  lastCheckedAt: string | null;
};

const api = {
  getBackendStatus: (): Promise<{
    status: "stopped" | "starting" | "healthy" | "error";
    error?: string | null;
    port: number;
    logFile?: string;
  }> => ipcRenderer.invoke("aic:get-backend-status"),
  getPaths: (): Promise<AicPaths> => ipcRenderer.invoke("aic:get-paths"),
  storeGet: (key?: string): Promise<unknown> => ipcRenderer.invoke("aic:store-get", key),
  storeSet: (key: string, value: unknown): Promise<boolean> =>
    ipcRenderer.invoke("aic:store-set", key, value),
  openPath: (target: string): Promise<{ ok: boolean; error?: string }> =>
    ipcRenderer.invoke("aic:open-path", target),
  showItem: (target: string): Promise<boolean> => ipcRenderer.invoke("aic:show-item", target),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke("aic:select-directory"),
  selectFile: (): Promise<string | null> => ipcRenderer.invoke("aic:select-file"),
  readDir: (dir: string): Promise<DirEntry[]> => ipcRenderer.invoke("aic:read-dir", dir),
  readDirTree: (dir: string, maxDepth?: number): Promise<DirTreeNode[]> =>
    ipcRenderer.invoke("aic:read-dir-tree", dir, maxDepth),
  readFile: (filePath: string): Promise<string> => ipcRenderer.invoke("aic:read-file", filePath),
  writeFile: (filePath: string, content: string): Promise<boolean> =>
    ipcRenderer.invoke("aic:write-file", filePath, content),
  createFile: (filePath: string): Promise<boolean> =>
    ipcRenderer.invoke("aic:create-file", filePath),
  deleteFile: (filePath: string): Promise<boolean> =>
    ipcRenderer.invoke("aic:delete-file", filePath),
  renameFile: (oldPath: string, newName: string): Promise<string> =>
    ipcRenderer.invoke("aic:rename-file", oldPath, newName),
  saveBlob: (filename: string, data: ArrayBuffer): Promise<string> =>
    ipcRenderer.invoke("aic:save-blob", filename, data),
  platformMod: (): Promise<string> => ipcRenderer.invoke("aic:platform-mod"),
  termStart: (cwd?: string): Promise<{ ok: boolean; shell: string; cwd: string }> =>
    ipcRenderer.invoke("aic:term-start", cwd),
  termWrite: (data: string): Promise<boolean> => ipcRenderer.invoke("aic:term-write", data),
  termKill: (): Promise<boolean> => ipcRenderer.invoke("aic:term-kill"),
  termResize: (cols: number, rows: number): Promise<boolean> =>
    ipcRenderer.invoke("aic:term-resize", cols, rows),
  onTermData: (cb: (data: string) => void): (() => void) => {
    const handler = (_: unknown, data: string) => cb(data);
    ipcRenderer.on("aic:term-data", handler);
    return () => ipcRenderer.removeListener("aic:term-data", handler);
  },

  // Auto Update
  getAppVersion: (): Promise<string> => ipcRenderer.invoke("aic:get-app-version"),
  updateGetState: (): Promise<UpdateStateDto | null> => ipcRenderer.invoke("aic:update-get-state"),
  updateGetConfig: (): Promise<UpdateConfigDto | null> => ipcRenderer.invoke("aic:update-get-config"),
  updateSetConfig: (partial: Partial<UpdateConfigDto>): Promise<UpdateConfigDto | null> =>
    ipcRenderer.invoke("aic:update-set-config", partial),
  updateCheck: (): Promise<void> => ipcRenderer.invoke("aic:update-check"),
  updateDownload: (): Promise<void> => ipcRenderer.invoke("aic:update-download"),
  updateInstall: (): Promise<void> => ipcRenderer.invoke("aic:update-install"),
  updateQuitAndInstall: (): Promise<void> => ipcRenderer.invoke("aic:update-quit-and-install"),
  updateDismiss: (): Promise<void> => ipcRenderer.invoke("aic:update-dismiss"),

  // Window controls
  minimize: (): Promise<boolean> => ipcRenderer.invoke("aic:minimize"),
  maximize: (): Promise<boolean> => ipcRenderer.invoke("aic:maximize"),
  close: (): Promise<boolean> => ipcRenderer.invoke("aic:close"),

  // Navigation from native menu

  onUpdateStateChanged: (cb: (state: UpdateStateDto) => void) => {
    const handler = (_e: any, s: UpdateStateDto) => cb(s);
    ipcRenderer.on("aic:update-state-changed", handler);
    return () => {
      ipcRenderer.off("aic:update-state-changed", handler);
    };
  },
  
  // Unsaved dialog support (for update restarts)
  showUnsavedDialog: (): Promise<"save_restart" | "restart" | "cancel"> => 
    ipcRenderer.invoke("aic:show-unsaved-dialog"),
  
  // Explicit workspace persistence
  workspaceSave: (): Promise<{ ok: boolean; error?: string }> =>
    ipcRenderer.invoke("aic:workspace-save"),
  workspaceHasUnsaved: (): Promise<boolean> => 
    ipcRenderer.invoke("aic:workspace-has-unsaved"),
  onNavigate: (cb: (view: string) => void): (() => void) => {
    const handler = (_: unknown, view: string) => cb(view);
    ipcRenderer.on("aic:navigate", handler);
    return () => ipcRenderer.removeListener("aic:navigate", handler);
  },
  onUpdateOpen: (cb: () => void): (() => void) => {
    const handler = () => cb();
    ipcRenderer.on("aic:update-open", handler);
    return () => ipcRenderer.removeListener("aic:update-open", handler);
  },
  onCommandPalette: (cb: () => void): (() => void) => {
    const handler = () => cb();
    ipcRenderer.on("aic:command-palette", handler);
    return () => ipcRenderer.removeListener("aic:command-palette", handler);
  }
};

contextBridge.exposeInMainWorld("aic", api);
export type AicBridge = typeof api;
