import { describe, expect, it } from "vitest";
import { isTerminal } from "./fsm";

// Mirror the phaseToStage logic from ProjectWorkspace
function phaseToStage(phase: string): string {
  const p = phase.toLowerCase();
  if (p === "created" || p === "investigate") return "discovery";
  if (p === "planning") return "planning";
  if (p === "implementation") return "execution";
  if (p === "verification") return "verification";
  if (p === "closeout" || p === "completed") return "delivery";
  return "discovery";
}

describe("ProjectWorkspace stage detection", () => {
  it("maps created to discovery", () => {
    expect(phaseToStage("created")).toBe("discovery");
  });

  it("maps investigate to discovery", () => {
    expect(phaseToStage("investigate")).toBe("discovery");
  });

  it("maps planning to planning", () => {
    expect(phaseToStage("planning")).toBe("planning");
  });

  it("maps implementation to execution", () => {
    expect(phaseToStage("implementation")).toBe("execution");
  });

  it("maps verification to verification", () => {
    expect(phaseToStage("verification")).toBe("verification");
  });

  it("maps closeout to delivery", () => {
    expect(phaseToStage("closeout")).toBe("delivery");
  });

  it("maps completed to delivery", () => {
    expect(phaseToStage("completed")).toBe("delivery");
  });

  it("maps unknown to discovery", () => {
    expect(phaseToStage("unknown_phase")).toBe("discovery");
  });
});

describe("task filter logic", () => {
  const tasks = [
    { id: "1", status: "completed", project_id: "p1", title: "A" },
    { id: "2", status: "implementation", project_id: "p1", title: "B" },
    { id: "3", status: "blocked", project_id: "p2", title: "C" },
    { id: "4", status: "planning", project_id: "p1", title: "D" },
  ];

  it("filters by project", () => {
    const filtered = tasks.filter((t) => t.project_id === "p1");
    expect(filtered).toHaveLength(3);
  });

  it("filters by active status", () => {
    const filtered = tasks.filter((t) => !isTerminal(t.status));
    expect(filtered).toHaveLength(2); // implementation + planning
  });

  it("filters by completed status", () => {
    const filtered = tasks.filter((t) => t.status.toLowerCase() === "completed");
    expect(filtered).toHaveLength(1);
  });

  it("filters by blocked status", () => {
    const filtered = tasks.filter((t) => t.status.toLowerCase() === "blocked");
    expect(filtered).toHaveLength(1);
  });

  it("filters by project AND status combined", () => {
    const filtered = tasks.filter((t) => t.project_id === "p1" && !isTerminal(t.status));
    expect(filtered).toHaveLength(2);
  });
});
