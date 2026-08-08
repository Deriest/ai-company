import { useCallback, useEffect, useRef, useState } from "react";
import "./styles/tailwind.css";
import { useBoot } from "./hooks/useBoot";
import { BootSplash } from "./components/BootSplash";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { WorkspaceView } from "./components/WorkspaceView";
import { ChatView } from "./components/ChatView";
import { LiveCompanyView } from "./components/LiveCompanyView";
import { SettingsView, type SettingsTab } from "./components/SettingsView";
import { MCPView } from "./components/MCPView";
import { SkillsView } from "./components/SkillsView";
import { PluginsView } from "./components/PluginsView";
import { OrchestrationView } from "./components/OrchestrationView";
import { WorkflowsView } from "./components/WorkflowsView";
import { JobsView } from "./components/JobsView";
import { MemoryView } from "./components/MemoryView";
import { RAGView } from "./components/RAGView";
import { AutomationView } from "./components/AutomationView";
import { OnboardingFlow } from "./components/auth/OnboardingFlow";
import { CommandPalette } from "./components/CommandPalette";
import { TerminalPanel } from "./components/Terminal";
import { profileApi, type LocalProfile } from "./lib/api/profile";
import type { ProjectRecord } from "./lib/api/projects";
import type { RestoredState, View } from "./types";

const navViews: View[] = ["home", "hermes", "live", "skills", "mcp", "plugins", "settings"];

/**
 * v2.4.0 — Local profile (no auth). First-launch onboarding → main dashboard.
 */
export function App() {
  const [profile, setProfile] = useState<LocalProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("home");
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("General");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [projectRoot, setProjectRoot] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [projectRefreshKey, setProjectRefreshKey] = useState(0);
  const [showFileTree, setShowFileTree] = useState(true);
  const [newSessionSignal, setNewSessionSignal] = useState(0);
  // Boot gate: the profile GET can fail when it races the still-booting engine.
  // Once boot completes we re-check once so returning users never land in
  // onboarding just because their profile fetch fired too early.
  const profileRetryRef = useRef(false);

  // Load profile on mount
  useEffect(() => {
    profileApi.get().then((p) => {
      setProfile(p);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // Load projectRoot and projectName from store
  useEffect(() => {
    window.aic?.storeGet?.("projectRoot").then((v) => {
      if (typeof v === "string" && v) setProjectRoot(v);
    }).catch(() => {});
    window.aic?.storeGet?.("projectName").then((v) => {
      if (typeof v === "string" && v) setProjectName(v);
    }).catch(() => {});
  }, []);

  // BUG-24: Wire the restore callback instead of leaving dead plumbing. Called
  // by useBoot during session restore to restore project root + conversation.
  const restoreRef = useRef<((stored: RestoredState) => void) | undefined>(undefined);
  restoreRef.current = (stored: RestoredState) => {
    if (stored.projectRoot) {
      setProjectRoot(stored.projectRoot);
      window.aic?.storeSet?.("projectRoot", stored.projectRoot).catch(() => {});
    }
    if (stored.conversationId) {
      try { sessionStorage.setItem("aic-ade-active-conversation", stored.conversationId); } catch {}
    }
  };

const boot = useBoot({
    onViewChange: useCallback((v: View) => setView(v), []),
    restoreRef,
  });

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // BUG-14: Don't hijack keys while typing in inputs/selects — except
      // Ctrl/Cmd+K which is the standard palette shortcut.
      const tag = (e.target as HTMLElement | null)?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen(o => !o);
        return;
      }
      if (typing) return;
      if ((e.metaKey || e.ctrlKey) && e.key === "`") {
        e.preventDefault();
        setShowTerminal(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && e.key >= "1" && e.key <= "7") {
        e.preventDefault();
        const idx = parseInt(e.key) - 1;
        if (navViews[idx]) setView(navViews[idx]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleOnboardingComplete = useCallback((p: LocalProfile) => {
    setProfile(p);
  }, []);

  const handleProjectChange = useCallback((project: ProjectRecord | null) => {
    if (project) {
      setProjectRoot(project.repo_path);
      setProjectName(project.name);
      window.aic?.storeSet?.("projectRoot", project.repo_path);
      window.aic?.storeSet?.("projectName", project.name);
    } else {
      setProjectRoot(null);
      setProjectName(null);
      window.aic?.storeSet?.("projectRoot", null);
      window.aic?.storeSet?.("projectName", null);
    }
    // Bump so every ProjectPicker instance (AppShell rail + Command Center)
    // reloads the active project and reflects the switch immediately.
    setProjectRefreshKey((k) => k + 1);
  }, []);

  const handleFileSelect = useCallback(async (path: string) => {
    await window.aic?.openPath?.(path);
  }, []);

  // Just-refreshed early profile check: the mount-time profileApi.get() can
  // fail when it races the still-booting engine. Once the engine is healthy,
  // re-check once so a returning user with a slow backend never falls through
  // to onboarding. Guarded so a genuinely-missing profile just shows onboarding.
  useEffect(() => {
    if (boot.bootPhase === "ready" && profile === null && !profileRetryRef.current) {
      profileRetryRef.current = true;
      profileApi.get().then((p) => {
        if (p) setProfile(p);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [boot.bootPhase, profile]);

  // Loading
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground animate-pulse">Loading…</div>
      </div>
    );
  }

  // Boot gate — block every screen until the local engine is healthy. On a
  // hard engine error the splash becomes an error panel with Retry/Open log
  // instead of a dead-end spinner.
  if (boot.bootPhase !== "ready") {
    return (
      <BootSplash
        phase={boot.bootPhase}
        detail={boot.bootDetail}
        backendStatus={boot.backendStatus}
        onRetry={boot.retryBoot}
      />
    );
  }

  // First launch — onboarding
  if (!profile || !profile.onboardingCompleted) {
    return <OnboardingFlow onComplete={handleOnboardingComplete} />;
  }

  // Main app
  const renderView = () => {
    switch (view) {
      case "home":
      case "welcome":
      case "overview":
        return <WorkspaceView onNavigate={(v) => setView(v as View)} projectRoot={projectRoot} projectName={projectName} showFileTree={showFileTree} onToggleFileTree={() => setShowFileTree(p => !p)} />;
      case "hermes":
      case "chat":
        return null;
      case "live":
        return <LiveCompanyView />;
      case "skills":
        return <SkillsView />;
      case "mcp":
        return <MCPView />;
      case "settings":
        return (
          <SettingsView
            initialTab={settingsTab}
            updateDialogOpen={boot.updateDialogOpen}
            onUpdateDialogOpenChange={boot.setUpdateDialogOpen}
            onProfileUpdated={(updated) =>
              // FE-H2: PATCH /profile returns only a partial profile
              // ({id, displayName, onboardingCompleted, githubToken}) — merge it
              // over the full profile instead of replacing it, so
              // deviceId/appVersion/createdAt survive the update.
              setProfile(prev => (prev ? { ...prev, ...updated } : updated))
            }
            onProjectRootChange={(root) => {
              // BUG-6: Workspace "Default Project Root" save must propagate to
              // App-level state and the IPC store.
              setProjectRoot(root);
              window.aic?.storeSet?.("projectRoot", root).catch(() => {});
            }}
          />
        );
      case "orchestration":
        return <OrchestrationView />;
      case "workflows":
        return <WorkflowsView />;
      case "jobs":
        return <JobsView />;
      case "memory":
        return <MemoryView />;
      case "rag":
        return <RAGView />;
      case "plugins":
        return <PluginsView />;
      case "automation":
        return <AutomationView />;
      default:
        return <WorkspaceView onNavigate={(v) => setView(v as View)} projectRoot={projectRoot} projectName={projectName} showFileTree={showFileTree} onToggleFileTree={() => setShowFileTree(p => !p)} />;
    }
  };

  return (
    <>
      <AppShell
        view={view}
        onViewChange={(v: string) => setView(v as View)}
        setSettingsTab={setSettingsTab as unknown as (tab: string) => void}
        profile={profile}
        projectRoot={projectRoot}
        projectRefreshKey={projectRefreshKey}
        onFileSelect={handleFileSelect}
        onProjectChange={handleProjectChange}
      >
        <div className="flex flex-1 min-h-0 flex-col">
          <div className="relative flex flex-1 min-h-0 flex-col">
            {/* Keep Command Center mounted while navigating so streaming state and
                the active conversation cannot disappear with the menu view. */}
            <div className={view === "hermes" || view === "chat" ? "flex flex-1 min-h-0 flex-col" : "hidden"}>
              <ChatView
                health={boot.health}
                currentProvider={boot.currentProvider}
                view={view}
                newSessionSignal={newSessionSignal}
                projectRoot={projectRoot}
                projectName={projectName}
                projectRefreshKey={projectRefreshKey}
                onProjectChange={handleProjectChange}
              />
            </div>
            <div className={view === "hermes" || view === "chat" ? "hidden" : "flex flex-1 min-h-0 flex-col"}>
              {/* Per-view boundary: a render error in one view shows a
                  "View failed to render" message instead of nuking the app.
                  resetKey={view} clears the boundary's error state on view
                  change WITHOUT remounting the subtree — views stay mounted
                  (CSS hidden) so scroll position, unsaved form fields and
                  in-flight fetches survive navigation. */}
              <ErrorBoundary resetKey={view} compact label="View failed to render">
                {renderView()}
              </ErrorBoundary>
            </div>
          </div>
          {showTerminal && (
            <TerminalPanel
              cwd={projectRoot || undefined}
              onClose={() => setShowTerminal(false)}
            />
          )}
        </div>
      </AppShell>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={(v) => setView(v as View)}
        onNewSession={() => {
          // BUG-5: "New Conversation" now creates a real conversation instead
          // of toggling the Terminal panel.
          setView("hermes");
          setNewSessionSignal(n => n + 1);
        }}
        onToggleTerminal={() => setShowTerminal(prev => !prev)}
        onToggleFileTree={() => setShowFileTree(p => !p)}
      />
    </>
  );
}
