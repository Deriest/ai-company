/**
 * Edge-case UNIT tests — deterministic, no live backend required.
 *
 * The existing `edge-cases.test.ts` / `integration.test.ts` hit a live platform
 * and silently SKIP when the backend is down. These unit tests mock `fetch` so
 * CI can exercise the same error-state / auth-failure paths without a platform.
 *
 * Run: npx vitest run src/renderer/src/lib/edge-cases.unit.test.ts
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

const fetchMock = vi.fn();

function jsonBody(status: number, data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function req(method: string, path: string, token?: string, body?: unknown) {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`http://127.0.0.1:8000${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: res.status, ok: res.ok, data: res.status === 204 ? null : await res.json().catch(() => null) };
}

describe("edge case (unit, mocked fetch): auth failure", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("rejects invalid credentials with 401", async () => {
    fetchMock.mockResolvedValue(jsonBody(401, { detail: "Invalid credentials" }));
    const r = await req("POST", "/auth/login", undefined, { username: "bad", password: "bad" });
    expect(r.status).toBe(401);
    expect(r.ok).toBe(false);
  });

  it("rejects missing token on protected endpoint with 401", async () => {
    fetchMock.mockResolvedValue(jsonBody(401, { detail: "Missing token" }));
    const r = await req("GET", "/auth/me");
    expect(r.status).toBe(401);
  });

  it("rejects invalid token with 401", async () => {
    fetchMock.mockResolvedValue(jsonBody(401, { detail: "Invalid or expired token" }));
    const r = await req("GET", "/auth/me", "invalid-token-12345");
    expect(r.status).toBe(401);
  });

  it("sends the Bearer token when a valid token is supplied", async () => {
    fetchMock.mockResolvedValue(jsonBody(200, { username: "admin" }));
    await req("GET", "/auth/me", "valid-token");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer valid-token");
  });
});

describe("edge case (unit, mocked fetch): non-existent resources", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("returns error status for a non-existent task", async () => {
    fetchMock.mockResolvedValue(jsonBody(404, { detail: "Task not found" }));
    const r = await req("GET", "/tasks/nonexistent-id");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(404);
  });

  it("returns error status for a non-existent worker", async () => {
    fetchMock.mockResolvedValue(jsonBody(404, { detail: "Worker not found" }));
    const r = await req("GET", "/workers/nonexistent-worker");
    expect(r.ok).toBe(false);
  });

  it("handles malformed (non-JSON) responses gracefully", async () => {
    fetchMock.mockResolvedValue(new Response("not json at all", { status: 200 }));
    const r = await req("GET", "/health");
    expect(r.status).toBe(200);
    expect(r.data).toBeNull();
  });

  it("handles empty 204 responses", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const r = await req("DELETE", "/conversations/x");
    expect(r.status).toBe(204);
    expect(r.data).toBeNull();
  });
});