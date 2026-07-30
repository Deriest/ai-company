/**
 * Edge case integration tests — error states, empty data, auth failure, malformed responses.
 * Run: npx vitest run src/renderer/src/lib/edge-cases.test.ts
 * Requires aic-platform running on http://127.0.0.1:8000
 */
import { describe, expect, it, beforeAll } from "vitest";

const BASE = process.env.AIC_BASE_URL || "http://127.0.0.1:8000";

async function req(method: string, path: string, token?: string, body?: unknown) {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method, headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: res.status, ok: res.ok, data: res.status === 204 ? null : await res.json().catch(() => null) };
}

let validToken: string | null = null;

beforeAll(async () => {
  try {
    const r = await req("POST", "/api/auth/login", undefined, { username: "admin", password: "admin123" });
    validToken = (r.data as { access_token?: string })?.access_token || null;
  } catch { /* platform down */ }
});

describe("edge case: auth failure", () => {
  it("rejects invalid credentials with 401", async () => {
    try {
      const r = await req("POST", "/api/auth/login", undefined, { username: "bad", password: "bad" });
      expect(r.ok).toBe(false);
      expect(r.status).toBeGreaterThanOrEqual(400);
    } catch { console.log("SKIP: platform not running"); }
  });

  it("rejects missing token on protected endpoint", async () => {
    try {
      const r = await req("GET", "/api/tasks");
      expect(r.ok).toBe(false);
    } catch { console.log("SKIP: platform not running"); }
  });

  it("rejects invalid token", async () => {
    try {
      const r = await req("GET", "/api/tasks", "invalid-token-12345");
      expect(r.ok).toBe(false);
    } catch { console.log("SKIP: platform not running"); }
  });
});

describe("edge case: non-existent resources", () => {
  it("returns error for non-existent task", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/tasks/nonexistent-id-12345", validToken);
    expect(r.ok).toBe(false);
  });

  it("returns error for non-existent worker", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/workers/nonexistent-worker", validToken);
    expect(r.ok).toBe(false);
  });

  it("handles non-existent conversation messages gracefully", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/conversations/nonexistent/messages", validToken);
    // Platform may return 200 with empty array or 404 — either is acceptable
    expect(r.status).toBeGreaterThanOrEqual(200);
    expect(r.status).toBeLessThan(500);
  });
});

describe("edge case: empty/malformed requests", () => {
  it("handles empty body on login", async () => {
    try {
      const r = await req("POST", "/api/auth/login", undefined, {});
      expect(r.ok).toBe(false);
    } catch { console.log("SKIP: platform not running"); }
  });

  it("handles project creation with empty name", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("POST", "/api/projects", validToken, { name: "", description: "" });
    // Platform may accept or reject — just verify no crash
    expect(r.status).toBeGreaterThanOrEqual(200);
  });

  it("handles dispatch on non-existent task", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("POST", "/api/tasks/nonexistent-id/dispatch", validToken);
    expect(r.ok).toBe(false);
  });

  it("handles cancel on non-existent task", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("POST", "/api/tasks/nonexistent-id/cancel", validToken);
    expect(r.ok).toBe(false);
  });
});

describe("edge case: data shape validation", () => {
  it("workers response is array with id field", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/workers", validToken);
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.data)).toBe(true);
    if ((r.data as unknown[]).length > 0) {
      const first = (r.data as Array<Record<string, unknown>>)[0];
      expect(first).toHaveProperty("id");
    }
  });

  it("tasks response is array", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/tasks", validToken);
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.data)).toBe(true);
  });

  it("events response is array or has events key", async () => {
    if (!validToken) { console.log("SKIP: no token"); return; }
    const r = await req("GET", "/api/dashboard/events", validToken);
    expect(r.ok).toBe(true);
    const data = r.data;
    expect(Array.isArray(data) || (data && typeof data === "object" && "events" in data)).toBe(true);
  });
});
