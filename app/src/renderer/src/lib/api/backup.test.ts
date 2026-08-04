import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { backupApi } from "./backup";

/**
 * backupApi tests. The apiClient resolves the backend port from window.aic
 * then fetches through the global fetch — both are stubbed here.
 */

function mockFetchJson<T>(data: T, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      text: async () => (ok ? JSON.stringify(data) : JSON.stringify({ detail: "boom" })),
    }),
  );
}

function lastFetchCall(): [string, RequestInit | undefined] {
  const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  return calls[calls.length - 1] as [string, RequestInit | undefined];
}

beforeEach(() => {
  (globalThis as any).window = {
    aic: {
      getBackendStatus: vi.fn().mockResolvedValue({ port: 8000 }),
    },
  };
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (globalThis as any).window;
});

describe("backupApi", () => {
  it("createBackup POSTs /backup/create and returns the record", async () => {
    const rec = { filename: "backup-2026-01-01.zip", size: 1234, created_at: "2026-01-01T00:00:00Z" };
    mockFetchJson(rec);

    const result = await backupApi.createBackup();

    expect(result).toEqual(rec);
    const [url, opts] = lastFetchCall();
    expect(url).toContain("/backup/create");
    expect(opts?.method).toBe("POST");
  });

  it("validateBackup POSTs the filename to /backup/validate", async () => {
    const res = { valid: true, version: "1.0", created_at: "2026-01-01T00:00:00Z", entries: 12 };
    mockFetchJson(res);

    const result = await backupApi.validateBackup("backup-2026-01-01.zip");

    expect(result).toEqual(res);
    const [url, opts] = lastFetchCall();
    expect(url).toContain("/backup/validate");
    expect(JSON.parse(String(opts?.body))).toEqual({ filename: "backup-2026-01-01.zip" });
  });

  it("listBackups GETs /backup/list and returns records", async () => {
    const list = [{ filename: "a.zip", size: 1, created_at: "2026-01-01T00:00:00Z" }];
    mockFetchJson(list);

    const result = await backupApi.listBackups();

    expect(result).toEqual(list);
    const [url, opts] = lastFetchCall();
    expect(url).toContain("/backup/list");
    expect(opts?.method).toBe("GET");
  });

  it("throws ApiClientError with the backend detail on non-2xx", async () => {
    mockFetchJson({ detail: "boom" }, false, 500);

    await expect(backupApi.listBackups()).rejects.toThrow("boom");
  });
});