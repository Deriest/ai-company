import { describe, it, expect } from "vitest";
import { bootstrapStepsForKind } from "./projectBootstrap";

describe("bootstrapStepsForKind", () => {
  it("node has install", () => {
    const steps = bootstrapStepsForKind("node");
    expect(steps[0].command).toContain("npm");
  });
  it("python has venv", () => {
    expect(bootstrapStepsForKind("python").some((s) => s.id === "venv")).toBe(true);
  });
  it("unknown empty", () => {
    expect(bootstrapStepsForKind("unknown")).toEqual([]);
  });
});
