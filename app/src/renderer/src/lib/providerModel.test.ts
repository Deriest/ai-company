import { describe, it, expect } from "vitest";
import {
  resolveDefaultModelId,
  formatModelLabel,
  activeProvider,
} from "./providerModel";

describe("providerModel helpers", () => {
  it("prefers explicit model field", () => {
    expect(
      resolveDefaultModelId({
        model: "gpt-4o-mini",
        models: { thinker: "other" },
      })
    ).toBe("gpt-4o-mini");
  });

  it("falls back to models.default then tiers", () => {
    expect(resolveDefaultModelId({ models: { default: "a", thinker: "b" } })).toBe("a");
    expect(resolveDefaultModelId({ models: { thinker: "b" } })).toBe("b");
  });

  it("formats model · provider label", () => {
    expect(
      formatModelLabel({ name: "OpenAI", model: "gpt-4o-mini", is_active: true })
    ).toBe("gpt-4o-mini · OpenAI");
  });

  it("shows configure when missing", () => {
    expect(formatModelLabel(null)).toBe("Configure Provider");
    expect(formatModelLabel({ name: "OpenRouter" })).toBe("Select model · OpenRouter");
  });

  it("selects active provider", () => {
    const list = [
      { id: "1", name: "A", is_active: false, model: "m1" },
      { id: "2", name: "B", is_active: true, model: "m2" },
    ];
    expect(activeProvider(list)?.id).toBe("2");
  });
});
