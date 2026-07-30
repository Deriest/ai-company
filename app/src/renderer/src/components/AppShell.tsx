import React, { useEffect, useRef, useState } from "react";
import {
  LayoutDashboard,
  Terminal,
  Users,
  Settings,
  Minus,
  Square,
  X,
  User,
  Bug,
  Info,
  Wrench,
  Plug,
  FolderTree,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "../lib/utils";
import { BugReportDialog } from "./auth/Dialogs";
import { FileTree } from "./FileTree";
import { ProjectPicker } from "./ProjectPicker";
import type { LocalProfile } from "../lib/api/profile";
import type { ProjectRecord } from "../lib/api/projects";

const nav = [
  { id: "home", label: "Office", icon: LayoutDashboard },
  { id: "hermes", label: "Command Center", icon: Terminal },
  { id: "live", label: "Live Company", icon: Users },
  { id: "skills", label: "Skills", icon: Wrench },
  { id: "mcp", label: "MCP Servers", icon: Plug },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

export function AppShell({
  children,
  view = "home",
  onViewChange,
  health = "ok",
  modelLabel = "OC/MIMO-V2.5-FREE",
  alertCount = 4,
  profile,
  setSettingsTab,
  projectRoot,
  onFileSelect,
  onProjectChange,
}: {
  children: React.ReactNode;
  view?: string;
  onViewChange?: (v: string) => void;
  health?: string;
  modelLabel?: string;
  alertCount?: number;
  profile?: LocalProfile | null;
  setSettingsTab?: (tab: string) => void;
  projectRoot?: string | null;
  onFileSelect?: (path: string) => void;
  onProjectChange?: (project: ProjectRecord | null) => void;
}) {
  const connected = health === "ok";
  const [menuOpen, setMenuOpen] = useState(false);
  const [bugOpen, setBugOpen] = useState(false);
  const [fileTreeOpen, setFileTreeOpen] = useState(true);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const initial = profile?.displayName?.charAt(0)?.toUpperCase() || "A";
  const name = profile?.displayName || "User";

  const goAccount = (tab: string) => {
    setMenuOpen(false);
    setSettingsTab?.(tab);
    onViewChange?.("settings");
  };

  return (
    <div className="flex h-svh flex-col overflow-hidden bg-background text-foreground">
      <header className="flex h-9 shrink-0 items-center justify-between border-b border-border bg-sidebar px-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <img src="/aic-ade-logo.png" alt="AIC ADE" width={18} height={18} className="rounded" />
            <span className="text-xs font-semibold tracking-wide">AIC ADE</span>
            <span className="text-xs text-muted-foreground">— AI Company Workspace</span>
          </div>
        </div>

        <div className="flex items-center gap-1 text-muted-foreground">
          <button type="button" className="grid size-6 place-items-center rounded hover:bg-muted" aria-label="Minimize" onClick={() => window.aic?.minimize?.()}>
            <Minus className="size-3.5" />
          </button>
          <button type="button" className="grid size-6 place-items-center rounded hover:bg-muted" aria-label="Maximize" onClick={() => window.aic?.maximize?.()}>
            <Square className="size-3" />
          </button>
          <button
            type="button"
            className="grid size-6 place-items-center rounded hover:bg-destructive hover:text-destructive-foreground"
            aria-label="Close"
            onClick={() => window.aic?.close?.()}
          >
            <X className="size-3.5" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
          <div className="flex items-center gap-2 px-4 py-4">
            <img src="/aic-ade-logo.png" alt="AIC ADE" width={32} height={32} className="rounded-lg" />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold">AIC ADE</span>
              <span className="text-[11px] text-muted-foreground">AI Company Workspace</span>
              <span className={cn("mt-0.5 flex items-center gap-1 text-[11px]", connected ? "text-success" : "text-destructive")}>
                <span className={cn("size-1.5 rounded-full", connected ? "bg-success" : "bg-destructive")} />
                {connected ? "Connected" : "Offline"}
              </span>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-3 py-2">
            {nav.map((item) => {
              const active =
                item.id === "home"
                  ? view === "home" || view === "welcome" || view === "overview"
                  : item.id === "hermes"
                    ? view === "hermes" || view === "chat"
                    : view === item.id;
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onViewChange?.(item.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className={cn("size-4", active && "text-primary")} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="border-t border-sidebar-border px-2 py-2">
            <ProjectPicker onProjectChange={onProjectChange} />
          </div>

          {projectRoot && (
            <div className="border-t border-sidebar-border">
              <button
                type="button"
                onClick={() => setFileTreeOpen(o => !o)}
                className="flex w-full items-center gap-2 px-4 py-2 text-[11px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {fileTreeOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                <FolderTree className="size-3.5" />
                Explorer
              </button>
              {fileTreeOpen && (
                <FileTree rootPath={projectRoot} onFileSelect={onFileSelect || (() => {})} />
              )}
            </div>
          )}

          <div className="relative border-t border-sidebar-border p-3" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-muted"
            >
              <div className="grid size-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                {initial}
              </div>
              <div className="flex min-w-0 flex-col leading-tight">
                <span className="truncate text-sm font-medium">{name}</span>
                <span className="flex items-center gap-1 text-[11px] text-success">
                  <span className="size-1.5 rounded-full bg-success" />
                  Online
                </span>
              </div>
            </button>
            <p className="px-2 pt-2 font-mono text-[10px] text-muted-foreground">v2.4.0</p>

            {menuOpen ? (
              <div className="absolute bottom-full left-3 right-3 z-50 mb-1 overflow-hidden rounded-xl border border-border bg-card py-1 shadow-lg">
                {[
                  { label: "Profile", icon: User, run: () => goAccount("General") },
                  { label: "About", icon: Info, run: () => goAccount("About") },
                  { label: "Report bug", icon: Bug, run: () => { setMenuOpen(false); setBugOpen(true); } },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={item.run}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted"
                  >
                    <item.icon className="size-3.5 text-muted-foreground" />
                    {item.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto scroll-thin">{children}</div>

          <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-sidebar px-4 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className={cn("size-1.5 rounded-full", connected ? "bg-success" : "bg-destructive")} />
              {connected ? "System operational" : "System offline"}
            </div>
            <div className="flex items-center gap-4">
              <span className="font-mono">{modelLabel}</span>
            </div>
          </footer>
        </main>
      </div>
      <BugReportDialog open={bugOpen} onClose={() => setBugOpen(false)} />
    </div>
  );
}
