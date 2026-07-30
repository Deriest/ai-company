import { useCallback, useEffect, useRef, useState } from "react";
import { api, configureClient } from "../lib/runtimeClient";
import { formatFriendlyError } from "../lib/errors";
import { detectProjectEnvironment, type ProjectEnvironmentHint } from "../lib/projectEnv";
import { isTerminal } from "../lib/fsm";
import type { DirTreeNode, View, RestoredState } from "../types";

export interface UseWorkspaceOptions {
  token: string | null;
  engineUrl: string;
  view: View;
  log: (line: string) => void;
  bootDone: React.MutableRefObject<boolean>;
  setError: (error: string | null) => void;
  onViewChange: (view: View) => void;
}

export interface WorkspaceState {
  // Project
  projectRoot: string | null;
  setProjectRoot: React.Dispatch<React.SetStateAction<string | null>>;
  projectEnv: ProjectEnvironmentHint | null;
  recentProjects: string[];
  setRecentProjects: React.Dispatch<React.SetStateAction<string[]>>;
  // Files
  fileTree: DirTreeNode[];
  openFilePath: string | null;
  setOpenFilePath: React.Dispatch<React.SetStateAction<string | null>>;
  openFileContent: string;
  setOpenFileContent: React.Dispatch<React.SetStateAction<string>>;
  fileDirty: boolean;
  setFileDirty: React.Dispatch<React.SetStateAction<boolean>>;
  openTabs: Array<{ path: string; content: string }>;
  setOpenTabs: React.Dispatch<React.SetStateAction<Array<{ path: string; content: string }>>>;
  fileSearch: string;
  setFileSearch: React.Dispatch<React.SetStateAction<string>>;
  // Trust
  trustedProjects: string[];
  setTrustedProjects: React.Dispatch<React.SetStateAction<string[]>>;
  pendingTrust: string | null;
  setPendingTrust: React.Dispatch<React.SetStateAction<string | null>>;
  // New project
  showNewProject: boolean;
  setShowNewProject: React.Dispatch<React.SetStateAction<boolean>>;
  newProjectName: string;
  setNewProjectName: React.Dispatch<React.SetStateAction<string>>;
  newProjectDesc: string;
  setNewProjectDesc: React.Dispatch<React.SetStateAction<string>>;
  creatingProject: boolean;
  // Terminal
  termOut: string;
  termInput: string;
  setTermInput: React.Dispatch<React.SetStateAction<string>>;
  termRunning: boolean;
  // Dock
  dockTab: "activity" | "output" | "problems" | "terminal";
  setDockTab: React.Dispatch<React.SetStateAction<"activity" | "output" | "problems" | "terminal">>;
  dockCollapsed: boolean;
  setDockCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  // Task filters
  taskFilterProject: string;
  setTaskFilterProject: React.Dispatch<React.SetStateAction<string>>;
  taskFilterStatus: string;
  setTaskFilterStatus: React.Dispatch<React.SetStateAction<string>>;
  // Data
  workers: unknown[] | null;
  projects: unknown[];
  tasks: unknown[];
  overview: Record<string, unknown> | null;
  // Selection
  selectedWorker: string | null;
  setSelectedWorker: React.Dispatch<React.SetStateAction<string | null>>;
  selectedTaskId: string | null;
  setSelectedTaskId: React.Dispatch<React.SetStateAction<string | null>>;
  selectedProjectId: string | null;
  setSelectedProjectId: React.Dispatch<React.SetStateAction<string | null>>;
  // Operations
  refreshAll: () => Promise<void>;
  openLocalProject: (dir?: string) => Promise<void>;
  doOpenProject: (folder: string) => Promise<void>;
  trustProject: (folder: string) => Promise<void>;
  loadDir: (dir: string) => Promise<void>;
  openLocalFile: (filePath: string, isDir: boolean) => Promise<void>;
  saveOpenFile: () => Promise<void>;
  renameFile: (path: string) => Promise<void>;
  deleteFile: (path: string) => Promise<void>;
  createFile: () => Promise<void>;
  createProject: () => Promise<void>;
  startTerm: () => Promise<void>;
  sendTerm: () => Promise<void>;
  killTerm: () => void;
  openTask: (id: string) => void;
  initFromStore: (stored: RestoredState) => void;
  // Helpers re-exported for views
  isTerminal: (status: string) => boolean;
}

export function useWorkspace(opts: UseWorkspaceOptions): WorkspaceState {
  const { token, engineUrl, view, log, bootDone, setError, onViewChange } = opts;

  const [projectRoot, setProjectRoot] = useState<string | null>(null);
  const [projectEnv, setProjectEnv] = useState<ProjectEnvironmentHint | null>(null);
  const [recentProjects, setRecentProjects] = useState<string[]>([]);
  const [fileTree, setFileTree] = useState<DirTreeNode[]>([]);
  const [openFilePath, setOpenFilePath] = useState<string | null>(null);
  const [openFileContent, setOpenFileContent] = useState("");
  const [fileDirty, setFileDirty] = useState(false);
  const [openTabs, setOpenTabs] = useState<Array<{ path: string; content: string }>>([]);
  const [fileSearch, setFileSearch] = useState("");
  const [trustedProjects, setTrustedProjects] = useState<string[]>([]);
  const [pendingTrust, setPendingTrust] = useState<string | null>(null);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [termOut, setTermOut] = useState("User project shell — open a folder, then Start shell.\n");
  const [termInput, setTermInput] = useState("");
  const [termRunning, setTermRunning] = useState(false);
  const [dockTab, setDockTab] = useState<"activity" | "output" | "problems" | "terminal">("activity");
  const [dockCollapsed, setDockCollapsed] = useState(false);
  const [taskFilterProject, setTaskFilterProject] = useState("");
  const [taskFilterStatus, setTaskFilterStatus] = useState("");
  const [workers, setWorkers] = useState<unknown[] | null>(null);
  const [projects, setProjects] = useState<unknown[]>([]);
  const [tasks, setTasks] = useState<unknown[]>([]);
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // ── Store restoration ──────────────────────────────────────────
  const initFromStore = useCallback((stored: RestoredState) => {
    if (stored.projectRoot) setProjectRoot(stored.projectRoot);
    setRecentProjects(stored.recentProjects);
    setTrustedProjects(stored.trustedProjects);
    setDockCollapsed(stored.dockCollapsed);
    if (stored.openTabs.length) setOpenTabs(stored.openTabs);
  }, []);

  // ── Data refresh ───────────────────────────────────────────────
  const refreshAll = useCallback(async () => {
    if (!token) return;
    configureClient({ baseUrl: engineUrl, token });
    try {
      const [w, p, t, ov] = await Promise.all([
        api.workers().catch(() => []),
        api.projects().catch(() => []),
        api.tasks({ limit: 100 }).catch(() => []),
        api.dashboard().catch(() => null),
      ]);
      setWorkers(Array.isArray(w) ? w : []);
      setProjects(Array.isArray(p) ? p : []);
      setTasks(Array.isArray(t) ? t : []);
      setOverview(ov && typeof ov === "object" ? (ov as Record<string, unknown>) : null);
    } catch (e) {
      if (bootDone.current) {
        const m = formatFriendlyError(e);
        if (m) setError(m);
      }
    }
  }, [token, engineUrl, bootDone, setError]);

  // RefreshAll interval
  useEffect(() => {
    if (!token) return;
    void refreshAll();
    const id = setInterval(() => void refreshAll(), 30000);
    return () => clearInterval(id);
  }, [token, refreshAll]);

  // ── Terminal data listener ─────────────────────────────────────
  useEffect(() => {
    if (!window.aic?.onTermData) return;
    return window.aic.onTermData((data) => {
      setTermOut((o) => (o + data).slice(-20000));
    });
  }, []);

  // ── File operations ────────────────────────────────────────────
  const loadDir = useCallback(
    async (dir: string) => {
      if (!window.aic) return;
      try {
        const tree = await window.aic.readDirTree(dir, 4);
        setFileTree(tree);
      } catch (e) {
        const m = formatFriendlyError(e);
        if (m) setError(m);
      }
    },
    [setError]
  );

  // Load file tree when entering files view with a project root
  useEffect(() => {
    if (view === "files" && projectRoot) void loadDir(projectRoot);
  }, [view, projectRoot, loadDir]);

  // ── Project operations ─────────────────────────────────────────
  const doOpenProjectRef = useRef<(folder: string) => Promise<void>>(undefined);

  const doOpenProject = useCallback(
    async (folder: string) => {
      setProjectRoot(folder);
      await window.aic?.storeSet("projectRoot", folder);
      setRecentProjects((prev) => {
        const next = [folder, ...prev.filter((p) => p !== folder)].slice(0, 10);
        void window.aic?.storeSet("recentProjects", next);
        return next;
      });
      log(`project root ${folder}`);
      try {
        if (window.aic) {
          const entries = await window.aic.readDir(folder);
          const names = (entries || []).map((e) => e.name);
          setProjectEnv(detectProjectEnvironment(names));
        }
      } catch {
        setProjectEnv(null);
      }
      onViewChange("files");
    },
    [log, onViewChange]
  );

  // Keep ref in sync
  doOpenProjectRef.current = doOpenProject;

  const openLocalProject = useCallback(
    async (dir?: string) => {
      let folder = dir;
      if (!folder) {
        if (!window.aic) {
          setError("Native bridge unavailable (run inside Electron)");
          return;
        }
        folder = (await window.aic.selectDirectory()) ?? undefined;
      }
      if (!folder) return;

      // Workspace trust: if not trusted, show trust dialog
      if (!trustedProjects.includes(folder)) {
        setPendingTrust(folder);
        return;
      }

      doOpenProjectRef.current?.(folder);
    },
    [trustedProjects, setError]
  );

  const trustProject = useCallback(async (folder: string) => {
    setTrustedProjects((prev) => {
      const next = [...prev, folder];
      void window.aic?.storeSet("trustedProjects", next);
      return next;
    });
    setPendingTrust(null);
    doOpenProjectRef.current?.(folder);
  }, []);

  const openLocalFile = useCallback(
    async (filePath: string, isDir: boolean) => {
      if (isDir) {
        await loadDir(filePath);
        return;
      }
      if (!window.aic) return;
      try {
        const content = await window.aic.readFile(filePath);
        const existing = openTabs.find((t) => t.path === filePath);
        if (!existing) {
          setOpenTabs((prev) => [...prev, { path: filePath, content }]);
        }
        setOpenFilePath(filePath);
        setOpenFileContent(content);
        setFileDirty(false);
      } catch (e) {
        const m = formatFriendlyError(e);
        if (m) setError(m);
      }
    },
    [loadDir, openTabs, setError]
  );

  const saveOpenFile = useCallback(async () => {
    if (!window.aic || !openFilePath) return;
    try {
      await window.aic.writeFile(openFilePath, openFileContent);
      setFileDirty(false);
      log(`saved ${openFilePath}`);
    } catch (e) {
      const m = formatFriendlyError(e);
      if (m) setError(m);
    }
  }, [openFilePath, openFileContent, log, setError]);

  const renameFile = useCallback(
    async (path: string) => {
      const newName = prompt("New name:", path.split("/").pop());
      if (newName && window.aic) {
        try {
          await window.aic.renameFile(path, newName);
          if (projectRoot) await loadDir(projectRoot);
        } catch (e) {
          setError(String(e));
        }
      }
    },
    [projectRoot, loadDir, setError]
  );

  const deleteFile = useCallback(
    async (path: string) => {
      if (window.aic) {
        try {
          await window.aic.deleteFile(path);
          if (projectRoot) await loadDir(projectRoot);
        } catch (e) {
          setError(String(e));
        }
      }
    },
    [projectRoot, loadDir, setError]
  );

  const createFile = useCallback(async () => {
    const name = prompt("New file name:");
    if (name && projectRoot) {
      const p = projectRoot + (projectRoot.endsWith("/") ? "" : "/") + name;
      try {
        await window.aic?.createFile(p);
        if (projectRoot) await loadDir(projectRoot);
      } catch (e) {
        setError(String(e));
      }
    }
  }, [projectRoot, loadDir, setError]);

  // ── Create project ─────────────────────────────────────────────
  const createProject = useCallback(async () => {
    setCreatingProject(true);
    setError(null);
    try {
      const result = await api.createProject(newProjectName.trim(), newProjectDesc.trim());
      log(`project created: ${newProjectName.trim()}`);
      setShowNewProject(false);
      setNewProjectName("");
      setNewProjectDesc("");
      void refreshAll();
      const pid = String((result as Record<string, unknown>)?.id || "");
      if (pid) {
        setSelectedProjectId(pid);
        onViewChange("workspace");
      }
    } catch (e) {
      const m = formatFriendlyError(e);
      if (m) setError(m);
    } finally {
      setCreatingProject(false);
    }
  }, [newProjectName, newProjectDesc, log, refreshAll, setError, onViewChange]);

  // ── Terminal ───────────────────────────────────────────────────
  const startTerm = useCallback(async () => {
    if (!window.aic) {
      setError("Shell requires Electron native bridge");
      return;
    }
    try {
      const r = await window.aic.termStart(projectRoot || undefined);
      setTermRunning(true);
      setTermOut((o) => o + `\n[started ${r.shell} in ${r.cwd}]\n`);
      setDockTab("terminal");
      setDockCollapsed(false);
      log("user shell started");
    } catch (e) {
      const m = formatFriendlyError(e);
      if (m) setError(m);
    }
  }, [projectRoot, log, setError]);

  const sendTerm = useCallback(async () => {
    if (!window.aic || !termInput) return;
    await window.aic.termWrite(termInput.endsWith("\n") ? termInput : termInput + "\n");
    setTermInput("");
  }, [termInput]);

  const killTerm = useCallback(() => {
    void window.aic?.termKill();
    setTermRunning(false);
  }, []);

  // ── Navigation helpers ─────────────────────────────────────────
  const openTask = useCallback(
    (id: string) => {
      setSelectedTaskId(id);
      onViewChange("projects");
    },
    [onViewChange]
  );

  // ── Tab persistence ────────────────────────────────────────────
  useEffect(() => {
    if (!bootDone.current) return;
    void window.aic?.storeSet(
      "openTabs",
      openTabs.map((t) => ({ path: t.path, content: t.content.slice(0, 200_000) }))
    );
  }, [openTabs, bootDone]);

  return {
    projectRoot,
    setProjectRoot,
    projectEnv,
    recentProjects,
    setRecentProjects,
    fileTree,
    openFilePath,
    setOpenFilePath,
    openFileContent,
    setOpenFileContent,
    fileDirty,
    setFileDirty,
    openTabs,
    setOpenTabs,
    fileSearch,
    setFileSearch,
    trustedProjects,
    setTrustedProjects,
    pendingTrust,
    setPendingTrust,
    showNewProject,
    setShowNewProject,
    newProjectName,
    setNewProjectName,
    newProjectDesc,
    setNewProjectDesc,
    creatingProject,
    termOut,
    termInput,
    setTermInput,
    termRunning,
    dockTab,
    setDockTab,
    dockCollapsed,
    setDockCollapsed,
    taskFilterProject,
    setTaskFilterProject,
    taskFilterStatus,
    setTaskFilterStatus,
    workers,
    projects,
    tasks,
    overview,
    selectedWorker,
    setSelectedWorker,
    selectedTaskId,
    setSelectedTaskId,
    selectedProjectId,
    setSelectedProjectId,
    refreshAll,
    openLocalProject,
    doOpenProject,
    trustProject,
    loadDir,
    openLocalFile,
    saveOpenFile,
    renameFile,
    deleteFile,
    createFile,
    createProject,
    startTerm,
    sendTerm,
    killTerm,
    openTask,
    initFromStore,
    isTerminal,
  };
}
