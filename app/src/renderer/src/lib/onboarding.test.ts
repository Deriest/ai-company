import { describe, it, expect } from "vitest";

type OnboardingState = {
  llmConfigured: boolean;
  token: string | null;
  currentView: string;
};

export function resolveStartupView(state: OnboardingState): string {
  if (!state.llmConfigured) {
    return "settings"; // Route to Guided Provider Setup
  }
  if (state.currentView === "welcome" && state.token) {
    return "overview"; // Direct to Home for returning configured user
  }
  return state.currentView;
}

describe("First-Launch & Returning User Onboarding Routing", () => {
  it("SCENARIO 1: routes brand new user without LLM provider to settings setup", () => {
    const view = resolveStartupView({
      llmConfigured: false,
      token: "valid-token",
      currentView: "overview",
    });
    expect(view).toBe("settings");
  });

  it("SCENARIO 2: routes returning user with valid LLM provider directly to Home (overview)", () => {
    const view = resolveStartupView({
      llmConfigured: true,
      token: "valid-token",
      currentView: "welcome",
    });
    expect(view).toBe("overview");
  });

  it("preserves active view if provider is configured", () => {
    const view = resolveStartupView({
      llmConfigured: true,
      token: "valid-token",
      currentView: "chat",
    });
    expect(view).toBe("chat");
  });
});
