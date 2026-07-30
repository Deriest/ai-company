/**
 * Centralized command registry — single source of truth for all commands.
 *
 * Every command has: id, label, category, optional shortcut, optional when-clause.
 * The command palette, keyboard handler, and native menu all derive from this registry.
 */

export type CommandCategory =
  | "Navigate"
  | "Mission"
  | "Workspace"
  | "Hermes"
  | "Live Company"
  | "Review"
  | "Window"
  | "Settings";

export interface CommandDef {
  id: string;
  label: string;
  category: CommandCategory;
  hint?: string;
  when?: () => boolean; // optional runtime guard
  run: () => void;
}

/**
 * Build the command list. Called once from App with bound callbacks.
 */
export function createCommands(ctx: {
  modKey: string;
  setView: (v: string) => void;
  openPalette: () => void;
  openLocalProject: () => void;
  startTerm: () => void;
  refreshHealth: () => void;
  refreshAll: () => void;
  toggleSidebar: () => void;
  togglePanel: () => void;
}): CommandDef[] {
  const m = ctx.modKey;
  return [
    // Navigate
    { id: "home", label: "Go to Home", category: "Navigate", hint: `${m}+1`, run: () => ctx.setView("home") },
    { id: "mission", label: "Go to Mission", category: "Navigate", hint: `${m}+2`, run: () => ctx.setView("mission") },
    { id: "workspace", label: "Go to Workspace", category: "Navigate", hint: `${m}+3`, run: () => ctx.setView("workspace") },
    { id: "hermes", label: "Go to Hermes", category: "Navigate", hint: `${m}+4`, run: () => ctx.setView("hermes") },
    { id: "live", label: "Go to Live Company", category: "Navigate", hint: `${m}+5`, run: () => ctx.setView("live") },
    { id: "review", label: "Go to Review Center", category: "Navigate", hint: `${m}+6`, run: () => ctx.setView("review") },
    { id: "settings", label: "Go to Settings", category: "Navigate", hint: `${m}+,`, run: () => ctx.setView("settings") },

    // Mission
    { id: "open-project", label: "Open Local Project Folder", category: "Mission", run: () => ctx.openLocalProject() },

    // Workspace
    { id: "term", label: "Start User Shell", category: "Workspace", run: () => ctx.startTerm() },

    // Window
    { id: "palette", label: "Command Palette", category: "Window", hint: `${m}+K`, run: () => ctx.openPalette() },
    { id: "toggle-sidebar", label: "Toggle Sidebar", category: "Window", hint: `${m}+B`, run: () => ctx.toggleSidebar() },
    { id: "toggle-panel", label: "Toggle Bottom Panel", category: "Window", hint: `${m}+J`, run: () => ctx.togglePanel() },

    // Settings
    { id: "refresh", label: "Refresh Runtime", category: "Settings", run: () => { ctx.refreshHealth(); ctx.refreshAll(); } },
  ];
}
