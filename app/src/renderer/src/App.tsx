import { useCallback, useEffect, useRef, useState } from "react";
import "./styles/tailwind.css";
import { useBoot } from "./hooks/useBoot";
import { AppShell } from "./components/AppShell";
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
import type { View } from "./types";

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
  const [showFileTree, setShowFileTree] = useState(true);
  const paletteRef = useRef<React.Dispatch<React.SetStateAction<boolean>>>(undefined);

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

  const boot = useBoot({
    onViewChange: setView,
    onOpenPalette: useCallback(() => paletteRef.current?.(true), []),
    restoreRef: { current: undefined },
  });
  paletteRef.current = setPaletteOpen;

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "`") {
        e.preventDefault();
        setShowTerminal(o => !o);
      }
      if ((e.metaKey || e.ctrlKey) && e.key >= "1" && e.key <= "6") {
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
  }, []);

  const handleFileSelect = useCallback(async (path: string) => {
    await window.aic?.openPath?.(path);
  }, []);

  // Loading
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground animate-pulse">Loading…</div>
      </div>
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
            onProfileUpdated={setProfile}
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
        health={boot.health === "ok" ? "ok" : "bad"}
        modelLabel={boot.modelLabel || "No model configured"}
        alertCount={0}
        projectRoot={projectRoot}
        onFileSelect={handleFileSelect}
        onProjectChange={handleProjectChange}
      >
        <div className="flex flex-1 min-h-0 flex-col">
          <div className="relative flex flex-1 min-h-0 flex-col">
            {/* Keep Command Center mounted while navigating so streaming state and
                the active conversation cannot disappear with the menu view. */}
            <div className={view === "hermes" || view === "chat" ? "flex flex-1 min-h-0 flex-col" : "hidden"}>
              <ChatView health={boot.health} currentProvider={boot.currentProvider} />
            </div>
            <div className={view === "hermes" || view === "chat" ? "hidden" : "flex flex-1 min-h-0 flex-col"}>
              {renderView()}
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
        onNewSession={() => setShowTerminal(true)}
        onToggleTerminal={() => setShowTerminal(prev => !prev)}
        onToggleFileTree={() => setShowFileTree(p => !p)}
      />
    </>
  );
}
