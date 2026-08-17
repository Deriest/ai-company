import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, configureClient, connectWs } from "../lib/runtimeClient";
import { activeProvider, formatModelLabel, type ProviderLike } from "../lib/providerModel";
import { INTERNAL_ENGINE_URL, pickStartupView } from "../lib/sessionRestore";
import { DESKTOP_IDENTITY } from "../../../shared/desktopIdentity";
import type { UpdateStateDto, View, BootPhase, RestoredState } from "../types";

export interface UseBootOptions {
  onViewChange: (view: View) => void;
  restoreRef: React.MutableRefObject<((stored: RestoredState) => void) | undefined>;
}

export interface BackendStatusInfo {
  status: "stopped" | "starting" | "healthy" | "error";
  error?: string | null;
  port: number;
  logFile?: string;
}

export interface BootState {
  bootPhase: BootPhase;
  bootDetail: string;
  setBootPhase: React.Dispatch<React.SetStateAction<BootPhase>>;
  setBootDetail: React.Dispatch<React.SetStateAction<string>>;
  /** Last known sidecar status from the main process (drives the splash/error UI). */
  backendStatus: BackendStatusInfo | null;
  /** Re-run the boot sequence (used by the splash "Retry" button). */
  retryBoot: () => void;
  updateState: UpdateStateDto | null;
  updateDialogOpen: boolean;
  setUpdateDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  health: "unknown" | "ok" | "bad";
  healthDetail: string;
  token: string | null;
  userLabel: string;
  modKey: string;
  llmConfigured: boolean | null;
  providers: ProviderLike[];
  modelMenuOpen: boolean;
  setModelMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  currentProvider: ProviderLike | null;
  modelLabel: string;
  activityLog: string[];
  palette: boolean;
  setPalette: React.Dispatch<React.SetStateAction<boolean>>;
  engineUrl: string;
  log: (line: string) => void;
  refreshProviders: () => Promise<void>;
  refreshHealth: () => Promise<void>;
  updateDownload: () => Promise<void>;
  updateDismiss: () => Promise<void>;
  updateInstall: () => Promise<void>;
}

export function useBoot(opts: UseBootOptions): BootState {
  const { onViewChange, restoreRef } = opts;

  const [bootPhase, setBootPhase] = useState<BootPhase>("launching");
  const [bootDetail, setBootDetail] = useState("Starting local engine…");
  const [backendStatus, setBackendStatus] = useState<BackendStatusInfo | null>(null);
  const [bootAttempt, setBootAttempt] = useState(0);
  const [updateState, setUpdateState] = useState<UpdateStateDto | null>(null);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [health, setHealth] = useState<"unknown" | "ok" | "bad">("unknown");
  const [healthDetail, setHealthDetail] = useState("checking…");
  const [token, setToken] = useState<string | null>(null);
  const [userLabel, setUserLabel] = useState("");
  const [modKey, setModKey] = useState("Ctrl");
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [providers, setProviders] = useState<ProviderLike[]>([]);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [activityLog, setActivityLog] = useState<string[]>(["AIC ADE session started"]);
  const [palette, setPalette] = useState(false);

  const engineUrl = INTERNAL_ENGINE_URL;

  const log = useCallback((line: string) => {
    const ts = new Date().toLocaleTimeString();
    setActivityLog((prev) => [`${ts}  ${line}`, ...prev].slice(0, 300));
  }, []);

  const currentProvider = useMemo(() => activeProvider(providers), [providers]);
  const modelLabel = useMemo(() => formatModelLabel(currentProvider), [currentProvider]);

  /** Splash "Retry" — reset transient boot state and re-run the whole sequence. */
  const retryBoot = useCallback(() => {
    setBootPhase("launching");
    // M3: the sidecar auto-restarts on a short delay; show a restarting state
    // while the poll loop gives it a grace period before declaring error again.
    setBootDetail("Restarting engine…");
    setHealth("unknown");
    setHealthDetail("checking…");
    setBackendStatus(null);
    setBootAttempt((n) => n + 1);
  }, []);

  const refreshProviders = useCallback(async () => {
    if (!token) return;
    try {
      configureClient({ baseUrl: engineUrl, token });
      const list = await api.listProviders();
      setProviders(Array.isArray(list) ? (list as ProviderLike[]) : []);
    } catch {
      /* keep previous */
    }
  }, [engineUrl, token]);

  const refreshHealth = useCallback(async () => {
    configureClient({ baseUrl: engineUrl, token });
    try {
      const h = await api.health();
      setHealth(["ok", "healthy"].includes(h.status || "") ? "ok" : "bad");
      const isLlmConfigured = Boolean(h.llm_configured);
      setLlmConfigured(isLlmConfigured);
      setHealthDetail(isLlmConfigured ? "Ready · model configured" : "Ready · add an AI provider");
      if (token) void refreshProviders();
    } catch {
      setHealth("bad");
      setHealthDetail("Starting…");
    }
  }, [engineUrl, token, refreshProviders]);

  // ── Boot sequence ──────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      setBootPhase("launching");
      setBootDetail("Launching local engineering engine…");
      setBackendStatus(null);

      // Wait for main-process sidecar when available. A hard "error" status
      // (missing python, spawn failure, health timeout) stops the boot and
      // surfaces an actionable error screen instead of hanging on "Loading…".
      if (window.aic?.getBackendStatus) {
        let lastStatus: BackendStatusInfo | null = null;
        // M3: after a retry the main process restarts the sidecar on a short
        // delay, so the very first polls can still see the stale pre-restart
        // "error" status. Give a retry a grace period ("Restarting engine…")
        // and require consecutive error polls before declaring failure again.
        const isRetry = bootAttempt > 0;
        const gracePolls = isRetry ? 8 : 0;   // ~2s for the auto-restart to kick in
        const errorsRequired = isRetry ? 2 : 1;  // consecutive error polls to declare failure
        let consecutiveErrors = 0;
        for (let i = 0; i < 40; i++) {
          try {
            const st = await window.aic.getBackendStatus();
            lastStatus = st;
            setBackendStatus(st);
            if (st.status === "healthy") break;
            if (st.status === "error") {
              consecutiveErrors += 1;
              // Only surface error panel after grace period + required consecutive errors
              if (i >= gracePolls && consecutiveErrors >= errorsRequired) {
                setBootPhase("error");
                setBootDetail(st.error || "Engine failed to start");
                return;
              }
            } else {
              consecutiveErrors = 0;
            }
            setBootDetail(
              isRetry && i < gracePolls
                ? "Restarting engine…"
                : i < 4 ? "Launching local engineering engine…" : "Waiting for engine health…",
            );
          } catch {
            /* keep polling */
          }
          await new Promise((r) => setTimeout(r, 250));
        }
        if (!lastStatus || lastStatus.status !== "healthy") {
          setBootPhase("error");
          setBootDetail(lastStatus?.error || "Local engine did not become healthy within 10 seconds");
          return;
        }
      }

      setBootPhase("restoring_session");
      setBootDetail("Restoring projects, tabs, and conversations…");

      const mod = window.aic ? await window.aic.platformMod() : "Ctrl";
      setModKey(mod === "Meta" ? "⌘" : "Ctrl");

      const stored = (window.aic ? await window.aic.storeGet() : {}) as Record<string, unknown>;
      // Always bind internal engine — never restore remote admin URLs
      configureClient({ baseUrl: engineUrl, token: null });
      if (window.aic) {
        await window.aic.storeSet("baseUrl", engineUrl);
        // scrub residual web-era secrets from store
        if (stored.password) await window.aic.storeSet("password", null);
      }

      // SECURITY: the JWT is kept strictly in-memory. It is NEVER written to
      // state.json or any disk-persistent store (storeSet("token", ...) is
      // deliberately removed). A fresh per-install login runs on every boot —
      // the identity comes from the main-process identity.json (or the dev
      // fallback), not from a stored token.
      let restoredToken: string | null = null;
      try {
        const identity = (await window.aic?.getIdentity?.()) ?? DESKTOP_IDENTITY;
        const res = await api.login(identity.username, identity.password);
        restoredToken = res.access_token;
        setToken(restoredToken);
        configureClient({ baseUrl: engineUrl, token: restoredToken });
        setUserLabel(res.username || res.user?.username || "you");
      } catch {
        setBootDetail("Engine not ready for sign-in yet");
      }

      // Restore workspace/chat state via callback
      const root = typeof stored?.projectRoot === "string" ? stored.projectRoot : null;
      const restoredTabs = Array.isArray(stored?.openTabs)
        ? (stored.openTabs as Array<{ path: string; content?: string }>)
            .filter((t) => t?.path)
            .map((t) => ({ path: t.path, content: t.content || "" }))
        : [];

      restoreRef.current?.({
        projectRoot: root,
        recentProjects: Array.isArray(stored?.recentProjects) ? stored.recentProjects as string[] : [],
        trustedProjects: Array.isArray(stored?.trustedProjects) ? stored.trustedProjects as string[] : [],
        dockCollapsed: typeof stored?.dockCollapsed === "boolean" ? stored.dockCollapsed : false,
        conversationId: typeof stored?.conversationId === "string" ? stored.conversationId : null,
        openTabs: restoredTabs,
      });

      const firstRun = !restoredToken && !(Array.isArray(stored?.recentProjects) && stored.recentProjects.length);
      const nextView = pickStartupView({
        lastView: typeof stored?.lastView === "string" ? stored.lastView : null,
        hasProject: Boolean(root),
        hasToken: Boolean(restoredToken),
        firstRun: Boolean(firstRun),
        llmConfigured: null,
      }) as View;
      onViewChange(nextView);

      setBootPhase("loading_workspace");
      setBootDetail(root ? `Workspace: ${root}` : "No project folder yet");
      setBootPhase("loading_skills");
      setBootDetail("Preparing skills and workforce…");
      setBootPhase("ready");
      setBootDetail("Ready");
    })().catch((e) => {
      setBootPhase("error");
      setBootDetail(e instanceof Error ? e.message : String(e));
    });
  }, [engineUrl, bootAttempt]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Update listeners ───────────────────────────────────────────
  useEffect(() => {
    if (!window.aic?.onUpdateStateChanged) return;
    const off = window.aic.onUpdateStateChanged((s) => setUpdateState(s));
    void window.aic.updateGetState?.().then((s) => s && setUpdateState(s)).catch(() => {});
    return () => {
      off?.();
    };
  }, []);

  // ── Health interval ────────────────────────────────────────────
  useEffect(() => {
    void refreshHealth();
    const id = setInterval(() => void refreshHealth(), 15000);
    return () => clearInterval(id);
  }, [refreshHealth]);

  // ── WS: debounce refresh to avoid cascading refetches ─────────
  const wsRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!token) return;
    configureClient({ baseUrl: engineUrl, token });
    return connectWs(
      "general",
      (msg) => {
        log(`ws ${JSON.stringify(msg).slice(0, 140)}`);
        // Debounce: coalesce WS bursts into a single refresh
        if (wsRefreshRef.current) clearTimeout(wsRefreshRef.current);
        wsRefreshRef.current = setTimeout(() => {
          void refreshHealth();
        }, 1500);
      },
      (s) => log(`ws ${s}`)
    );
  }, [token, engineUrl, log, refreshHealth]);

  // ── Update actions ─────────────────────────────────────────────
  const updateDownload = useCallback(async () => {
    const s = await window.aic?.updateDownload?.();
    if (s) setUpdateState(s);
  }, []);

  const updateDismiss = useCallback(async () => {
    const s = await window.aic?.updateDismiss?.();
    if (s) setUpdateState(s);
  }, []);

  const updateInstall = useCallback(async () => {
    const s = await window.aic?.updateInstall?.();
    if (s) setUpdateState(s);
  }, []);

  return {
    bootPhase,
    bootDetail,
    setBootPhase,
    setBootDetail,
    backendStatus,
    retryBoot,
    updateState,
    updateDialogOpen,
    setUpdateDialogOpen,
    health,
    healthDetail,
    token,
    userLabel,
    modKey,
    llmConfigured,
    providers,
    modelMenuOpen,
    setModelMenuOpen,
    currentProvider,
    modelLabel,
    activityLog,
    palette,
    setPalette,
    engineUrl,
    log,
    refreshProviders,
    refreshHealth,
    updateDownload,
    updateDismiss,
    updateInstall,
  };
}
