import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  WORKFLOW_PHASES,
  WORKFLOWS,
  getWorkflow,
  primaryWorkflows,
  secondaryWorkflows,
  derivePhaseIndex,
  readPreferredWorkflow,
  writePreferredWorkflow,
  PREFERRED_WORKFLOW_STORAGE_KEY,
} from "./workflows";

describe("WORKFLOW_PHASES — mirrors backend WORKFLOW_PLANS", () => {
  it("bugfix skips discovery/planning/closeout", () => {
    expect(WORKFLOW_PHASES.bugfix).toEqual(["investigate", "implementation", "verification"]);
  });

  it("bughunt is read-only: investigate + verification, no implementation", () => {
    expect(WORKFLOW_PHASES.bughunt).toEqual(["investigate", "verification"]);
    expect(WORKFLOW_PHASES.bughunt).not.toContain("implementation");
  });

  it("test runs verification only", () => {
    expect(WORKFLOW_PHASES.test).toEqual(["verification"]);
  });

  it("docs lands in closeout only", () => {
    expect(WORKFLOW_PHASES.docs).toEqual(["closeout"]);
  });

  it("research stops after investigate + planning (no implementation)", () => {
    expect(WORKFLOW_PHASES.research).toEqual(["investigate", "planning"]);
    expect(WORKFLOW_PHASES.research).not.toContain("implementation");
  });

  it("build/feature run the full lifecycle", () => {
    const full = ["discovery", "investigate", "planning", "implementation", "verification", "closeout"];
    expect(WORKFLOW_PHASES.build).toEqual(full);
    expect(WORKFLOW_PHASES.feature).toEqual(full);
  });

  it("infra has no discovery and no closeout", () => {
    expect(WORKFLOW_PHASES.infra).not.toContain("discovery");
    expect(WORKFLOW_PHASES.infra).not.toContain("closeout");
  });
});

describe("WORKFLOWS catalog", () => {
  it("every workflow def has a unique type and required display fields", () => {
    const seen = new Set<string>();
    for (const wf of WORKFLOWS) {
      expect(seen.has(wf.type)).toBe(false);
      seen.add(wf.type);
      expect(wf.label).toBeTruthy();
      expect(wf.description).toBeTruthy();
      expect(wf.example).toBeTruthy();
      expect(wf.pipeline).toBeTruthy();
    }
  });

  it("getWorkflow returns the matching def and undefined for unknown", () => {
    expect(getWorkflow("bugfix")?.label).toBe("Fix Bug");
    expect(getWorkflow("nonexistent" as never)).toBeUndefined();
  });

  it("primary + secondary partition the full list", () => {
    const primary = primaryWorkflows();
    const secondary = secondaryWorkflows();
    expect(primary.length + secondary.length).toBe(WORKFLOWS.length);
    expect(primary.every(w => w.primary)).toBe(true);
    expect(secondary.every(w => !w.primary)).toBe(true);
  });

  it("primary list is within the 4-6 card range for the selector grid", () => {
    const n = primaryWorkflows().length;
    expect(n).toBeGreaterThanOrEqual(4);
    expect(n).toBeLessThanOrEqual(6);
  });
});

describe("derivePhaseIndex — stepper progress mapping", () => {
  it("queued maps to -1 (not started)", () => {
    expect(derivePhaseIndex("bugfix", "queued", 0.5)).toBe(-1);
  });

  it("completed maps past the last phase", () => {
    const phases = WORKFLOW_PHASES.bugfix;
    expect(derivePhaseIndex("bugfix", "completed", 0)).toBe(phases.length);
  });

  it("executing with 0 activity starts at phase 0", () => {
    expect(derivePhaseIndex("bugfix", "executing", 0)).toBe(0);
  });

  it("executing with high activity clamps to the last allowed phase", () => {
    const phases = WORKFLOW_PHASES.bughunt; // 2 phases
    expect(derivePhaseIndex("bughunt", "executing", 1)).toBe(phases.length - 1);
    expect(derivePhaseIndex("bughunt", "executing", 5)).toBe(phases.length - 1);
  });

  it("unknown status maps to -1", () => {
    expect(derivePhaseIndex("build", "weird-status", 0.5)).toBe(-1);
  });

  it("unknown workflow type falls back to the build plan", () => {
    const buildLen = WORKFLOW_PHASES.build.length;
    expect(derivePhaseIndex("nonexistent" as never, "completed", 0)).toBe(buildLen);
  });
});

describe("preferred workflow persistence (localStorage)", () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => { store.set(k, v); },
      removeItem: (k: string) => { store.delete(k); },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("returns null when nothing is stored", () => {
    expect(readPreferredWorkflow()).toBeNull();
  });

  it("round-trips a valid workflow type", () => {
    writePreferredWorkflow("bugfix");
    expect(readPreferredWorkflow()).toBe("bugfix");
  });

  it("rejects an invalid stored value and returns null", () => {
    store.set(PREFERRED_WORKFLOW_STORAGE_KEY, JSON.stringify({ type: "not-a-workflow" }));
    expect(readPreferredWorkflow()).toBeNull();
  });

  it("tolerates a bare string value", () => {
    store.set(PREFERRED_WORKFLOW_STORAGE_KEY, JSON.stringify("research"));
    expect(readPreferredWorkflow()).toBe("research");
  });

  it("tolerates corrupt JSON without throwing", () => {
    store.set(PREFERRED_WORKFLOW_STORAGE_KEY, "{not-json");
    expect(() => readPreferredWorkflow()).not.toThrow();
    expect(readPreferredWorkflow()).toBeNull();
  });
});
