import { describe, it, expect, vi, afterEach } from "vitest";
import { mapProfile, profileApi } from "./profile";
import { ApiClientError } from "./client";

/**
 * FE-H1 (github token shape normalization) + FE-H4 (404 detection by status).
 *
 * The client hits the network through global fetch; we stub fetch with fake
 * Response-shaped objects so no backend is needed.
 */

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("mapProfile — github token normalization (FE-H1)", () => {
  it("exposes the backend camelCase githubToken", () => {
    const p = mapProfile({
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      githubToken: "***",
    });
    expect(p.githubToken).toBe("***");
  });

  it("tolerates legacy snake_case github_token from older backends", () => {
    const p = mapProfile({
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      github_token: "***",
    });
    expect(p.githubToken).toBe("***");
  });

  it("prefers camelCase when both shapes are present", () => {
    const p = mapProfile({ githubToken: "***", github_token: "legacy" });
    expect(p.githubToken).toBe("***");
  });

  it("leaves githubToken absent when the backend omits it", () => {
    const p = mapProfile({ id: "p1", displayName: "Ada" });
    expect("githubToken" in p).toBe(false);
  });

  it("does not inject missing fields on partial payloads (FE-H2 merge safety)", () => {
    // PATCH /profile returns a partial shape — mapProfile must not fill absent
    // fields with defaults, or merging over the full profile would clobber it.
    const p = mapProfile({
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      githubToken: "***",
    });
    expect(p.deviceId).toBeUndefined();
    expect(p.appVersion).toBeUndefined();
    expect(p.createdAt).toBeUndefined();
    expect(p.lastSeen).toBeUndefined();
  });
});

describe("profileApi.get — 404 detection by status (FE-H4)", () => {
  it("returns null on HTTP 404 even when the detail text has no '404'", async () => {
    mockFetch(404, { detail: "No profile — first launch" });
    expect(await profileApi.get()).toBeNull();
  });

  it("does not treat a 500 whose detail mentions '404' as missing (old message-match bug)", async () => {
    // The old check (e.message.includes("404")) would wrongly return null here,
    // because it matched the backend detail text instead of the HTTP status.
    mockFetch(500, { detail: "upstream returned 404" });
    await expect(profileApi.get()).rejects.toBeInstanceOf(ApiClientError);
  });

  it("maps a full profile (including githubToken) on 200", async () => {
    mockFetch(200, {
      id: "p1",
      displayName: "Ada",
      deviceId: "dev-1",
      appVersion: "2.4.9",
      onboardingCompleted: true,
      githubToken: "***",
      createdAt: "2026-01-01T00:00:00Z",
      lastSeen: "2026-01-02T00:00:00Z",
    });
    const p = await profileApi.get();
    expect(p).not.toBeNull();
    expect(p?.displayName).toBe("Ada");
    expect(p?.deviceId).toBe("dev-1");
    expect(p?.githubToken).toBe("***");
  });
});

describe("profileApi.update — wire conversion (FE-H1 write side)", () => {
  it("sends githubToken as snake_case github_token on PATCH", async () => {
    const fetchMock = mockFetch(200, {
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      githubToken: "***",
    });
    await profileApi.update({ githubToken: "ghp_secret" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.github_token).toBe("ghp_secret");
    expect("githubToken" in body).toBe(false);
  });

  it("omits github_token entirely when githubToken is not provided (keeps stored)", async () => {
    const fetchMock = mockFetch(200, {
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      githubToken: "***",
    });
    await profileApi.update({ displayName: "Ada Lovelace" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect("github_token" in body).toBe(false);
  });

  it('sends "" to clear the stored token', async () => {
    const fetchMock = mockFetch(200, {
      id: "p1",
      displayName: "Ada",
      onboardingCompleted: true,
      githubToken: "",
    });
    await profileApi.update({ githubToken: "" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.github_token).toBe("");
  });
});
