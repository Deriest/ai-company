/**
 * Workflow UX definitions — mirrors backend WORKFLOW_PLANS (workflow/triage.py)
 * and EXECUTION_PHASES (workflow/fsm.py).
 *
 * The backend executes tasks through a phase pipeline. Each task_type is allowed
 * a subset of phases; phases not in the plan are skipped. This file keeps the
 * display metadata (icons, labels, descriptions, example prompts) and the
 * allowed-phase ordering so the frontend stepper can show ONLY the phases a
 * given workflow actually runs — never a full pipeline for a bugfix.
 */

import type { WorkflowType } from "./api/chat";

/** Canonical execution phase order (subset of fsm.EXECUTION_PHASES). */
export const EXECUTION_PHASES = [
  "discovery",
  "investigate",
  "planning",
  "implementation",
  "verification",
  "closeout",
] as const;

export type ExecutionPhase = (typeof EXECUTION_PHASES)[number];

/**
 * Mirrors backend WORKFLOW_PLANS: task_type -> allowed execution phases.
 * Any phase not listed for a type is skipped by the backend; the stepper
 * reflects only the allowed ones.
 */
export const WORKFLOW_PHASES: Record<WorkflowType, ExecutionPhase[]> = {
  build: ["discovery", "investigate", "planning", "implementation", "verification", "closeout"],
  feature: ["discovery", "investigate", "planning", "implementation", "verification", "closeout"],
  bugfix: ["investigate", "implementation", "verification"],
  refactor: ["investigate", "implementation", "verification"],
  bughunt: ["investigate", "verification"],
  test: ["verification"],
  docs: ["closeout"],
  infra: ["investigate", "planning", "implementation", "verification"],
  research: ["investigate", "planning"],
};

/** Human-readable phase labels for the stepper. */
export const PHASE_LABELS: Record<ExecutionPhase, string> = {
  discovery: "Discovering",
  investigate: "Investigating",
  planning: "Planning",
  implementation: "Implementing",
  verification: "Verifying",
  closeout: "Finalizing",
};

/** Display metadata for each workflow type (icon key, label, description, example). */
export interface WorkflowDef {
  type: WorkflowType;
  /** Short human label shown on the card. */
  label: string;
  /** Icon key — mapped to a lucide icon in the component. */
  icon: "hammer" | "bug" | "scan" | "sparkles" | "test" | "book" | "search" | "server";
  /** One-line description of what the workflow does. */
  description: string;
  /** A longer description for the onboarding screen. */
  detail: string;
  /** Example prompt to pre-fill the composer. */
  example: string;
  /** Tooltip explaining what the pipeline will do. */
  pipeline: string;
  /** Whether this workflow appears in the primary card grid (vs "More…"). */
  primary: boolean;
}

/** The most common workflows surfaced as cards. */
export const WORKFLOWS: WorkflowDef[] = [
  {
    type: "build",
    label: "Build / Create",
    icon: "hammer",
    description: "Build a new feature or app from scratch",
    detail:
      "Full lifecycle: discover requirements, plan the architecture, implement, verify, and finalize. Best for greenfield features and large changes.",
    example: "Build a REST API for a todo app with CRUD endpoints and tests",
    pipeline: "Discovery → Investigate → Plan → Implement → Verify → Finalize",
    primary: true,
  },
  {
    type: "bugfix",
    label: "Fix Bug",
    icon: "bug",
    description: "Diagnose and fix a specific bug",
    detail:
      "Investigate the root cause, implement the fix, and run a regression check. Skips formal planning and closeout for speed.",
    example: "Fix the login button not submitting the form on mobile",
    pipeline: "Investigate → Implement → Verify (regression)",
    primary: true,
  },
  {
    type: "bughunt",
    label: "Audit / Bug Hunt",
    icon: "scan",
    description: "Find issues in code — no changes made",
    detail:
      "Read-only audit: investigate and verify. The audit team hunts for bugs, security and quality issues without modifying code.",
    example: "Audit this module for potential security vulnerabilities",
    pipeline: "Investigate → Verify (read-only audit, no code changes)",
    primary: true,
  },
  {
    type: "refactor",
    label: "Improve / Maintain",
    icon: "sparkles",
    description: "Refactor while keeping behavior intact",
    detail:
      "Restructure and improve code quality without changing observable behavior. Investigate, restructure, then verify nothing broke.",
    example: "Refactor the payment service to use dependency injection",
    pipeline: "Investigate → Implement → Verify (behavior preserved)",
    primary: true,
  },
  {
    type: "test",
    label: "Test",
    icon: "test",
    description: "Write or run tests only",
    detail:
      "Verification-only workflow: run existing tests or generate new ones. No implementation or planning phases.",
    example: "Write unit tests for the user authentication module",
    pipeline: "Verify only (test generation / execution)",
    primary: true,
  },
  {
    type: "research",
    label: "Research",
    icon: "search",
    description: "Investigate and analyze — stop before building",
    detail:
      "Investigate the problem space and plan an approach, then stop. Ideal for feasibility studies and design exploration before committing to code.",
    example: "Research the best way to add real-time updates to this app",
    pipeline: "Investigate → Plan (stops before implementation)",
    primary: true,
  },
  {
    type: "docs",
    label: "Docs",
    icon: "book",
    description: "Write or update documentation",
    detail:
      "Documentation-only workflow that lands in the closeout phase — generates READMEs, guides, and inline docs.",
    example: "Write a README and API docs for this project",
    pipeline: "Finalize (documentation generation)",
    primary: false,
  },
  {
    type: "infra",
    label: "Infra",
    icon: "server",
    description: "Infrastructure, CI/CD, deployment",
    detail:
      "Infrastructure workflow: investigate, plan, implement, and verify. No discovery phase and no docs closeout.",
    example: "Set up a Docker Compose config and CI pipeline for this repo",
    pipeline: "Investigate → Plan → Implement → Verify",
    primary: false,
  },
];

/** Lookup a workflow definition by type. Returns undefined for unknown types. */
export function getWorkflow(type: WorkflowType): WorkflowDef | undefined {
  return WORKFLOWS.find(w => w.type === type);
}

/** Primary (card-grid) workflows. */
export function primaryWorkflows(): WorkflowDef[] {
  return WORKFLOWS.filter(w => w.primary);
}

/** Secondary ("More…") workflows. */
export function secondaryWorkflows(): WorkflowDef[] {
  return WORKFLOWS.filter(w => !w.primary);
}

/**
 * Map a backend status/event to an execution phase index within a workflow's
 * allowed phases. Returns -1 when no phase matches yet (queued/not started).
 *
 * The backend only emits coarse statuses today (queued / executing / completed),
 * so the stepper derives phase progress from the workflow's plan plus the
 * stream activity: as the agent runs tools and emits content, it advances
 * through the allowed phases. `activity` is a 0..1 progress signal derived
 * from tool-call/content activity in the stream.
 */
export function derivePhaseIndex(
  type: WorkflowType,
  status: "queued" | "executing" | "completed" | string,
  activity: number,
): number {
  const phases = WORKFLOW_PHASES[type] ?? WORKFLOW_PHASES.build;
  if (status === "queued") return -1;
  if (status === "completed") return phases.length; // past the last phase
  if (status !== "executing") return -1;
  // During execution, map the 0..1 activity signal onto the allowed phases.
  const clamped = Math.min(Math.max(activity, 0), 1);
  const idx = Math.floor(clamped * phases.length);
  return Math.min(idx, phases.length - 1);
}

/** localStorage + profile key for the user's preferred workflow. */
export const PREFERRED_WORKFLOW_STORAGE_KEY = "aic-ade-preferred-workflow";

/**
 * Read the preferred workflow from localStorage. Returns null when unset or
 * invalid so callers can fall back to a default.
 */
export function readPreferredWorkflow(): WorkflowType | null {
  try {
    const raw = localStorage.getItem(PREFERRED_WORKFLOW_STORAGE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    const t = typeof v === "string" ? v : v?.type;
    return WORKFLOWS.some(w => w.type === t) ? (t as WorkflowType) : null;
  } catch {
    return null;
  }
}

/** Persist the preferred workflow to localStorage. */
export function writePreferredWorkflow(type: WorkflowType): void {
  try {
    localStorage.setItem(PREFERRED_WORKFLOW_STORAGE_KEY, JSON.stringify({ type }));
  } catch {
    /* storage unavailable — preference simply won't persist */
  }
}
