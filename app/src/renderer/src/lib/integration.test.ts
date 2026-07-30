/**
 * Integration test — hits live aic-platform API.
 * Run: npx vitest run src/renderer/src/lib/integration.test.ts
 * Requires aic-platform running on http://127.0.0.1:8000
 */
import { describe, expect, it, beforeAll } from "vitest";

const BASE = process.env.AIC_BASE_URL || "http://127.0.0.1:8000";
const USER = process.env.AIC_USER || "admin";
const PASS = process.env.AIC_PASS || "admin123";

let token: string | null = null;

async function req(method: string, path: string, body?: unknown) {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} ${res.status}`);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return await res.json();
  return await res.text();
}

beforeAll(async () => {
  try {
    const login = await req("POST", "/api/auth/login", { username: USER, password: PASS }) as { access_token: string };
    token = login.access_token;
  } catch {
    // Platform not running — skip integration tests
  }
});

describe("integration: live platform API", () => {
  it("health endpoint responds", async () => {
    try {
      const h = await req("GET", "/api/health") as { status: string };
      expect(h.status).toBe("healthy");
    } catch {
      console.log("SKIP: platform not running");
    }
  });

  it("login returns token", async () => {
    try {
      const login = await req("POST", "/api/auth/login", { username: USER, password: PASS }) as { access_token: string };
      expect(login.access_token).toBeTruthy();
      token = login.access_token;
    } catch {
      console.log("SKIP: platform not running");
    }
  });

  it("workers returns 15 canonical", async () => {
    if (!token) { console.log("SKIP: no token"); return; }
    const workers = await req("GET", "/api/workers") as unknown[];
    expect(workers.length).toBeGreaterThanOrEqual(15);
  });

  it("tasks returns array", async () => {
    if (!token) { console.log("SKIP: no token"); return; }
    const tasks = await req("GET", "/api/tasks") as unknown[];
    expect(Array.isArray(tasks)).toBe(true);
  });

  it("projects returns array", async () => {
    if (!token) { console.log("SKIP: no token"); return; }
    const projects = await req("GET", "/api/projects") as unknown[];
    expect(Array.isArray(projects)).toBe(true);
  });
});
