import { describe, it, expect } from "vitest";
import { pickStartupView, isSafeView } from "./sessionRestore";

describe("pickStartupView", () => {
  it("shows welcome on first run without provider", () => {
    expect(pickStartupView({ firstRun: true, hasToken: false, llmConfigured: null })).toBe("welcome");
  });

  it("routes first-run without LLM to settings", () => {
    expect(pickStartupView({ firstRun: true, hasToken: false, llmConfigured: false })).toBe("settings");
  });

  it("restores last non-welcome view", () => {
    expect(
      pickStartupView({ lastView: "workspace", hasToken: true, hasProject: true, llmConfigured: true })
    ).toBe("workspace");
  });

  it("prefers files when project open and no last view", () => {
    expect(pickStartupView({ hasToken: true, hasProject: true, llmConfigured: true })).toBe("files");
  });

  it("defaults to overview when signed in without project", () => {
    expect(pickStartupView({ hasToken: true, hasProject: false, llmConfigured: true })).toBe("overview");
  });

  it("ignores welcome as lastView when has session", () => {
    expect(
      pickStartupView({ lastView: "welcome", hasToken: true, hasProject: false, llmConfigured: true })
    ).toBe("overview");
  });

  it("routes to settings when provider missing on returning session", () => {
    expect(
      pickStartupView({ hasToken: true, hasProject: false, llmConfigured: false })
    ).toBe("settings");
  });
});

describe("isSafeView", () => {
  it("accepts chat and workspace", () => {
    expect(isSafeView("chat")).toBe(true);
    expect(isSafeView("workspace")).toBe(true);
  });
  it("rejects unknown", () => {
    expect(isSafeView("admin-panel")).toBe(false);
  });
});
