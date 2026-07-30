import type { AicBridge, DirTreeNode, UpdateStateDto } from "../../preload/preload";

export type { DirTreeNode, UpdateStateDto };

/** Primary navigation destinations (7 rail items). */
export type PrimaryView =
  | "home"
  | "hermes"
  | "live"
  | "skills"
  | "mcp"
  | "settings";

/** Active view — primary or legacy (auto-mapped). */
export type View = PrimaryView | string;

export type Msg = { role: "user" | "assistant"; content: string };

export type BootPhase =
  | "launching"
  | "loading_workspace"
  | "restoring_session"
  | "loading_skills"
  | "ready"
  | "error";

/** Shape of values restored from persistent store during boot. */
export interface RestoredState {
  projectRoot: string | null;
  recentProjects: string[];
  trustedProjects: string[];
  dockCollapsed: boolean;
  conversationId: string | null;
  openTabs: Array<{ path: string; content: string }>;
}

declare global {
  interface Window {
    aic?: AicBridge;
  }
}
