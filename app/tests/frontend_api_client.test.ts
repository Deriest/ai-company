/**
 * Unit tests for the frontend API client token propagation.
 *
 * Covers the previously-untested auth plumbing in
 * `src/renderer/src/lib/api/client.ts` and `src/renderer/src/lib/runtimeClient.ts`:
 *   - setApiToken() results in `Authorization: Bearer <token>` on subsequent fetches
 *   - configureClient() pushes the token to the shared apiClient
 *   - getApiToken() retrieves the current token
 *   - ApiClientError surfaces non-2xx status codes
 *
 * `window.fetch` is mocked so no real network calls are made and the tests are
 * deterministic and runnable without a live backend.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

import {
  setApiToken,
  getApiToken,
  invalidateBaseUrlCache,
  apiClient,
} from "../src/renderer/src/lib/api/client";
import { configureClient } from "../src/renderer/src/lib/runtimeClient";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiClient token propagation", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    setApiToken(null);
    invalidateBaseUrlCache();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("setApiToken makes subsequent fetches carry Authorization: Bearer", async () => {
    setApiToken("token-abc-123");
    await apiClient.get("/health");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/health");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-abc-123");
  });

  it("no token set means no Authorization header is sent", async () => {
    await apiClient.get("/health");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("getApiToken returns the value set by setApiToken", () => {
    setApiToken("abc");
    expect(getApiToken()).toBe("abc");
    setApiToken(null);
    expect(getApiToken()).toBeNull();
  });

  it("configureClient pushes its token to the shared apiClient", async () => {
    configureClient({ baseUrl: "http://127.0.0.1:8000", token: "cfg-token" });
    expect(getApiToken()).toBe("cfg-token");

    await apiClient.get("/providers");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer cfg-token");
  });

  it("configureClient with null token clears the Authorization header", async () => {
    setApiToken("old-token");
    configureClient({ baseUrl: "http://127.0.0.1:8000", token: null });

    await apiClient.get("/health");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("apiClient.post sends JSON body and Bearer token together", async () => {
    setApiToken("t");
    await apiClient.post("/conversations", { title: "hi" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer t");
    expect(headers["Content-Type"]).toContain("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ title: "hi" });
  });

  it("non-2xx responses surface as ApiClientError with status", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "nope" }, 401));
    await expect(apiClient.get("/protected")).rejects.toMatchObject({
      status: 401,
      message: "nope",
    });
  });
});