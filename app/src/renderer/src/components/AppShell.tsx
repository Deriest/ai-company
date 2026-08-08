import React, { useEffect, useRef, useState } from "react";
import {
  LayoutDashboard,
  Terminal,
  Users,
  Settings,
  User,
  Bug,
  Wrench,
  Plug,
  GitBranch,
} from "lucide-react";
import { cn } from "../lib/utils";
import { BugReportDialog } from "./auth/Dialogs";
import TitleBar from "./TitleBar";
import type { LocalProfile } from "../lib/api/profile";

const nav = [
  { id: "home", label: "Office", icon: LayoutDashboard },
  { id: "hermes", label: "Command Center", icon: Terminal },
  { id: "live", label: "Live Company", icon: Users },
  { id: "skills", label: "Skills", icon: Wrench },
  { id: "mcp", label: "MCP Servers", icon: Plug },
  { id: "plugins", label: "Plugins", icon: GitBranch },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

export function AppShell({
  children,
  view = "home",
  onViewChange,
  profile,
  setSettingsTab,
}: {
  children: React.ReactNode;
  view?: string;
  onViewChange?: (v: string) => void;
  profile?: LocalProfile | null;
  setSettingsTab?: (tab: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [bugOpen, setBugOpen] = useState(false);
  const [appVersion, setAppVersion] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.aic?.getAppVersion?.().then((v: string) => {
      if (v) setAppVersion(v);
    }).catch(() => {});
  }, []);

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
      <TitleBar />
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-48 lg:w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar overflow-y-auto">
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
            <p className="px-2 pt-2 font-mono text-[10px] text-muted-foreground">{appVersion ? `v${appVersion}` : ''}</p>

            {menuOpen ? (
              <div className="absolute bottom-full left-3 right-3 z-50 mb-1 overflow-hidden rounded-xl border border-border bg-card py-1 shadow-lg">
                {[
                  { label: "Profile", icon: User, run: () => goAccount("General") },
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
          <div className="flex-1 min-h-0 flex flex-col relative">{children}</div>
        </main>
      </div>
      <BugReportDialog open={bugOpen} onClose={() => setBugOpen(false)} />
    </div>
  );
}
