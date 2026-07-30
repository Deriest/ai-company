import { describe, expect, it } from "vitest";
import { groupTasksByPhase, isTerminal, normalizePhase, phaseIndex, PHASE_ORDER } from "./fsm";
import { CANONICAL_WORKFORCE } from "./workforce";
import { normalizeWorkspaceFiles } from "./runtimeClient";

describe("fsm", () => {
  it("has ordered phases", () => {
    expect(PHASE_ORDER[0]).toBe("created");
    expect(PHASE_ORDER.at(-1)).toBe("completed");
  });

  it("normalizes and indexes", () => {
    expect(normalizePhase(" Planning ")).toBe("planning");
    expect(phaseIndex("implementation")).toBeGreaterThan(phaseIndex("investigate"));
    expect(isTerminal("completed")).toBe(true);
    expect(isTerminal("blocked")).toBe(true);
    expect(isTerminal("planning")).toBe(false);
  });

  it("groups tasks by status phase", () => {
    const buckets = groupTasksByPhase([
      { id: "1", status: "implementation", title: "A" },
      { id: "2", status: "IMPLEMENTATION", title: "B" },
      { id: "3", status: "completed", title: "C" },
    ]);
    expect(buckets.implementation).toHaveLength(2);
    expect(buckets.completed).toHaveLength(1);
  });
});

describe("workforce", () => {
  it("has exactly 15 canonical workers including Hermes", () => {
    expect(CANONICAL_WORKFORCE).toHaveLength(15);
    expect(CANONICAL_WORKFORCE.some((w) => w.id === "hermes")).toBe(true);
    expect(CANONICAL_WORKFORCE.some((w) => w.id === "security")).toBe(true);
    const ids = new Set(CANONICAL_WORKFORCE.map((w) => w.id));
    expect(ids.size).toBe(15);
  });
});

describe("normalizeWorkspaceFiles", () => {
  it("accepts string arrays and object arrays", () => {
    expect(normalizeWorkspaceFiles(["a.md", "b.md"])).toEqual(["a.md", "b.md"]);
    expect(normalizeWorkspaceFiles([{ path: "x/y" }, { name: "z" }])).toEqual(["x/y", "z"]);
    expect(normalizeWorkspaceFiles({ files: ["f"] })).toEqual(["f"]);
  });
});
