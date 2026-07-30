import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, configureClient, connectWs } from "../lib/runtimeClient";
import { activeProvider, formatModelLabel, type ProviderLike } from "../lib/providerModel";
import { INTERNAL_ENGINE_URL, pickStartupView } from "../lib/sessionRestore";
import { DESKTOP_IDENTITY } from "../../../shared/desktopIdentity";
import type { UpdateStateDto, View, BootPhase, RestoredState } from "../types";

export interface UseBootOptions {
  onViewChange: (view: View) => void;
  onOpenPalette: () => void;
  restoreRef: React.MutableRefObject<((stored: RestoredState) => void) | undefined>;
}

export interface BootState {
  bootPhase: BootPhase;
  bootDetail: string;
  setBootPhase: React.Dispatch<React.SetStateAction<BootPhase>>;
  setBootDetail: React.Dispatch<React.SetStateAction<string>>;
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
  bootDone: React.MutableRefObject<boolean>;
  engineUrl: string;
  log: (line: string) => void;
  refreshProviders: () => Promise<void>;
  refreshHealth: () => Promise<void>;
  workspaceRefreshRef: React.MutableRefObject<(() => Promise<void>) | undefined>;
  updateDownload: () => Promise<void>;
  updateDismiss: () => Promise<void>;
  updateInstall: () => Promise<void>;
}

export function useBoot(opts: UseBootOptions): BootState {
  const { onViewChange, onOpenPalette, restoreRef } = opts;

  const [bootPhase, setBootPhase] = useState<BootPhase>("launching");
  const [bootDetail, setBootDetail] = useState("Starting local engine…");
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
  const bootDone = useRef(false);
  const workspaceRefreshRef = useRef<(() => Promise<void>) | undefined>(undefined);

  const engineUrl = INTERNAL_ENGINE_URL;

  const log = useCallback((line: string) => {
    const ts = new Date().toLocaleTimeString();
    setActivityLog((prev) => [`${ts}  ${line}`, ...prev].slice(0, 300));
  }, []);

  const currentProvider = useMemo(() => activeProvider(providers), [providers]);
  const modelLabel = useMemo(() => formatModelLabel(currentProvider), [currentProvider]);

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

      // Wait for main-process sidecar when available
      if (window.aic?.getBackendStatus) {
        for (let i = 0; i < 40; i++) {
          try {
            const st = await window.aic.getBackendStatus();
            if (st.status === "healthy") break;
            if (st.status === "error") {
              setBootDetail(st.error || "Engine failed to start");
            } else {
              setBootDetail(i < 4 ? "Launching local engineering engine…" : "Waiting for engine health…");
            }
          } catch {
            /* keep polling */
          }
          await new Promise((r) => setTimeout(r, 250));
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

      let restoredToken: string | null = null;
      if (typeof stored?.token === "string" && stored.token) {
        configureClient({ baseUrl: engineUrl, token: stored.token });
        try {
          await api.me();
          restoredToken = stored.token;
          setToken(restoredToken);
        } catch {
          // Token is stale or JWT secret changed — clear stale token immediately
          restoredToken = null;
          setToken(null);
          if (window.aic) await window.aic.storeSet("token", null);
        }
      }

      if (!restoredToken) {
        try {
          const res = await api.login(DESKTOP_IDENTITY.username, DESKTOP_IDENTITY.password);
          restoredToken = res.access_token;
          setToken(restoredToken);
          configureClient({ baseUrl: engineUrl, token: restoredToken });
          setUserLabel(res.username || res.user?.username || "you");
          if (window.aic) {
            await window.aic.storeSet("token", restoredToken);
          }
        } catch {
          setBootDetail("Engine not ready for sign-in yet");
        }
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

      const firstRun = !stored?.token && !(Array.isArray(stored?.recentProjects) && stored.recentProjects.length);
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
      await new Promise((r) => setTimeout(r, 120));
      setBootPhase("loading_skills");
      setBootDetail("Preparing skills and workforce…");
      await new Promise((r) => setTimeout(r, 80));
      bootDone.current = true;
      setBootPhase("ready");
      setBootDetail("Ready");
    })().catch((e) => {
      setBootPhase("error");
      setBootDetail(e instanceof Error ? e.message : String(e));
    });
  }, [engineUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Update / navigation / palette listeners ────────────────────
  useEffect(() => {
    if (!window.aic?.onUpdateStateChanged) return;
    const off = window.aic.onUpdateStateChanged((s) => setUpdateState(s));
    void window.aic.updateGetState?.().then((s) => s && setUpdateState(s));
    const offNav = window.aic.onNavigate?.((v) => {
      if (v) onViewChange(v as View);
    });
    const offPalette = window.aic.onCommandPalette?.(() => onOpenPalette());
    const offUpdateOpen = window.aic.onUpdateOpen?.(() => setUpdateDialogOpen(true));
    return () => {
      off?.();
      offNav?.();
      offPalette?.();
      offUpdateOpen?.();
    };
  }, [onViewChange, onOpenPalette]);

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
          void workspaceRefreshRef.current?.();
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
    bootDone,
    engineUrl,
    log,
    refreshProviders,
    refreshHealth,
    workspaceRefreshRef,
    updateDownload,
    updateDismiss,
    updateInstall,
  };
}
