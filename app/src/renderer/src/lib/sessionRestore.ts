/** Session restore helpers — workspace-first desktop UX. */

export type RestorableView =
  | "welcome"
  | "overview"
  | "chat"
  | "projects"
  | "skills"
  | "live"
  | "board"
  | "files"
  | "approvals"
  | "delivery"
  | "activity"
  | "requirements"
  | "workspace"
  | "topology"
  | "orchestration"
  | "verification"
  | "problems"
  | "settings";

const SAFE_VIEWS: RestorableView[] = [
  "welcome",
  "overview",
  "chat",
  "projects",
  "skills",
  "live",
  "board",
  "files",
  "approvals",
  "delivery",
  "activity",
  "requirements",
  "workspace",
  "topology",
  "orchestration",
  "verification",
  "problems",
  "settings",
];

/** Prefer Hermes / workspace over welcome when user already has work. */
export function pickStartupView(opts: {
  lastView?: string | null;
  hasProject?: boolean;
  hasToken?: boolean;
  firstRun?: boolean;
  llmConfigured?: boolean | null;
}): RestorableView {
  // First-run without provider → settings (guided setup), not an empty home
  if (opts.firstRun || !opts.hasToken) {
    if (opts.llmConfigured === false) return "settings";
    return "welcome";
  }
  // Returning user still missing provider
  if (opts.llmConfigured === false) return "settings";
  const last = opts.lastView as RestorableView | undefined;
  if (last && SAFE_VIEWS.includes(last) && last !== "welcome") return last;
  if (opts.hasProject) return "files"; // local folder = files workspace, not abstract pipeline
  return "overview";
}

export function isSafeView(v: string): v is RestorableView {
  return SAFE_VIEWS.includes(v as RestorableView);
}

export const INTERNAL_ENGINE_URL = "http://127.0.0.1:8000";
