import { describe, it, expect } from "vitest";
import { friendlyError, formatFriendlyError } from "./errors";

describe("friendlyError", () => {
  it("maps Failed to fetch", () => {
    const f = friendlyError(new Error("Failed to fetch"));
    expect(f.title).toMatch(/engine/i);
    expect(f.retryable).toBe(true);
  });

  it("maps 401 as retryable session error (shown to user)", () => {
    const f = friendlyError(new Error("GET /api/x → 401: Could not validate credentials"));
    expect(f.silent).toBeFalsy();
    expect(f.retryable).toBe(true);
    expect(f.title.toLowerCase()).toMatch(/session|expired/);
  });

  it("maps model discovery 502", () => {
    const f = friendlyError(new Error("GET /api/llm/providers/x/models → 502: Failed to fetch models: timeout"));
    expect(f.title.toLowerCase()).toMatch(/provider|request/);
  });

  it("formatFriendlyError is non-empty", () => {
    expect(formatFriendlyError("ECONNREFUSED")).toMatch(/engine|listening|something/i);
  });
});
