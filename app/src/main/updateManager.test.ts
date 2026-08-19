import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { UpdateManager, type IO, type AppAdapter, type UpdateState } from "./updateManager";

// Mock global fetch to prevent real network calls during tests.
// Signature .sig files should return non-OK so the unsigned policy applies.
const originalFetch = global.fetch;
global.fetch = vi.fn(async (input: string | URL | Request): Promise<Response> => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  if (url.endsWith(".sig")) {
    return { ok: false } as Response;
  }
  return originalFetch(input);
});

vi.mock("../shared/updateSecurity", () => ({
  verifyManifestSignature: vi.fn(() => true),
  getVerificationStatus: vi.fn(() => ({ hasPublicKey: false, publicKeyLength: null, nodeEnv: "development", allowUnsigned: true })),
}));

// The module imports { app, shell, Notification } from "electron"; in a plain
// Node vitest run that import would return the electron binary path string, so
// we stub the module. All code-under-test uses the injected appAdapter/io
// seams, so these defaults are never exercised — they only keep the import
// from crashing.
vi.mock("electron", () => {
  class MockNotification {
    static isSupported = () => false;
    constructor(_opts: unknown) {}
    show() {}
  }
  return {
    app: {
      getVersion: () => "0.0.0",
      getPath: () => "/tmp/fake-userData",
      isPackaged: true,
      exit: vi.fn(),
      quit: vi.fn(),
      relaunch: vi.fn(),
    },
    shell: { openPath: vi.fn(async () => ""), openExternal: vi.fn(async () => {}) },
    Notification: MockNotification,
  };
});

const CURRENT_VERSION = "1.0.0";

function makeManifest(overrides: Record<string, unknown> = {}) {
  return {
    version: "2.0.0",
    channel: "stable",
    releaseNotes: "release notes",
    platforms: {
      linux: {
        downloadUrl: "https://example.com/aic.AppImage",
        sha256: "AA",
        size: 100,
        filename: "aic.AppImage",
        type: "AppImage",
      },
    },
    ...overrides,
  };
}

function makeMocks() {
  const io: IO = {
    fetchJson: vi.fn(async () => makeManifest()),
    downloadFile: vi.fn(async () => {}),
    sha256File: vi.fn(async () => "aa"),
  };
  const openPath = vi.fn(async (_p: string) => "");
  const appAdapter = {
    getVersion: vi.fn(() => CURRENT_VERSION),
    getPath: vi.fn(() => "/tmp/fake-userData"),
    shell: { openPath, openExternal: vi.fn(async () => {}) },
    Notification: class MockNotification {
      static isSupported = vi.fn(() => false);
      constructor(_opts: { title: string; body: string }) {}
      show() {}
    },
    exit: vi.fn(),
    quit: vi.fn(),
    relaunch: vi.fn(),
  } as unknown as AppAdapter;
  // (io, appAdapter) injection style — also exercises the constructor's
  // io-shape detection.
  const manager = new UpdateManager(io, appAdapter);
  return { io, appAdapter, openPath, manager };
}

let originalPlatform: string;
const tmpDirs: string[] = [];

beforeEach(() => {
  originalPlatform = process.platform;
  delete process.env.AIC_UPDATE_BASE_URL;
  delete process.env.AIC_DOWNLOAD_BASE_URL;
});

afterEach(() => {
  global.fetch = originalFetch;
  Object.defineProperty(process, "platform", { value: originalPlatform, configurable: true });
  for (const dir of tmpDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

function setPlatform(platform: string): void {
  Object.defineProperty(process, "platform", { value: platform, configurable: true });
}

describe("UpdateManager.checkForUpdates", () => {
  it("reports up_to_date when the remote version is not newer", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "1.0.0" }));

    const state = await manager.checkForUpdates();

    expect(state.status).toBe("up_to_date");
    expect(state.availableVersion).toBeUndefined();
  });

  it("reports available with artifact when a newer version exists", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "2.0.0" }));

    const state = await manager.checkForUpdates();

    expect(state.status).toBe("available");
    expect(state.availableVersion).toBe("2.0.0");
    expect(state.artifact?.filename).toBe("aic.AppImage");
    expect(state.releaseNotes).toBe("release notes");
  });

  it("flags the update as mandatory via manifest.mandatory", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "2.0.0", mandatory: true }));

    const state = await manager.checkForUpdates();

    expect(state.status).toBe("available");
    expect(state.mandatory).toBe(true);
  });

  it("flags the update as mandatory via minimumVersion above current", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "2.0.0", minimumVersion: "1.5.0" }));

    const state = await manager.checkForUpdates();

    expect(state.mandatory).toBe(true);
  });

  it("reports error when the manifest fetch fails", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockRejectedValue(new Error("ECONNREFUSED"));

    const state = await manager.checkForUpdates();

    expect(state.status).toBe("error");
    expect(state.error).toMatch(/Update check failed: ECONNREFUSED/);
  });

  it("reports error when no artifact exists for the current platform", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "2.0.0", platforms: {} }));

    const state = await manager.checkForUpdates();

    expect(state.status).toBe("error");
    expect(state.error).toMatch(/No update package for platform/);
  });
});

describe("UpdateManager.dismiss", () => {
  it("dismisses a non-mandatory available update", async () => {
    const { manager } = makeMocks();
    await manager.checkForUpdates();
    expect(manager.getState().status).toBe("available");

    manager.dismiss();

    const state = manager.getState();
    expect(state.status).toBe("idle");
    expect(state.dismissedVersion).toBe("2.0.0");
  });

  it("blocks dismissal while a mandatory update is available", async () => {
    const { manager, io } = makeMocks();
    vi.mocked(io.fetchJson).mockResolvedValue(makeManifest({ version: "2.0.0", mandatory: true }));
    await manager.checkForUpdates();
    expect(manager.getState().mandatory).toBe(true);

    manager.dismiss();

    expect(manager.getState().status).toBe("available");
  });
});

describe("UpdateManager.setConfig", () => {
  it("applies a valid https base URL", () => {
    const { manager } = makeMocks();
    manager.setConfig({ baseUrl: "https://mirror.example.com/updates" });
    expect(manager.getConfig().baseUrl).toBe("https://mirror.example.com/updates");
  });

  it("rejects an invalid base URL and keeps the previous one", () => {
    const { manager } = makeMocks();
    const before = manager.getConfig().baseUrl;

    expect(() => manager.setConfig({ baseUrl: "ftp://insecure.example.com" })).toThrow();

    const after = manager.getConfig();
    expect(after.baseUrl).toBe(before);
  });
});

describe("UpdateManager.installUpdate", () => {
  async function installViaDownload(platform: string, filename: string) {
    setPlatform(platform);
    const userData = fs.mkdtempSync(path.join(os.tmpdir(), "upd-test-"));
    tmpDirs.push(userData);
    const io: IO = {
      fetchJson: vi.fn(async () =>
        makeManifest({
          version: "9.0.0",
          platforms: {
            [platform]: {
              downloadUrl: "https://example.com/x",
              sha256: "AA",
              size: 1,
              filename,
              type: filename.endsWith(".AppImage") ? "AppImage" : "dmg",
            },
          },
        })
      ),
      downloadFile: vi.fn(async (_url: string, dest: string) => {
        fs.writeFileSync(dest, "payload");
      }),
      sha256File: vi.fn(async () => "aa"),
    };
    const openPath = vi.fn(async (_p: string) => "");
    const appAdapter = {
      getVersion: vi.fn(() => CURRENT_VERSION),
      getPath: vi.fn(() => userData),
      shell: { openPath, openExternal: vi.fn(async () => {}) },
      Notification: class MockNotification {
        static isSupported = vi.fn(() => false);
        constructor(_opts: { title: string; body: string }) {}
        show() {}
      },
      exit: vi.fn(),
      quit: vi.fn(),
      relaunch: vi.fn(),
    } as unknown as AppAdapter;
    const manager = new UpdateManager(io, appAdapter);
    await manager.checkForUpdates();
    await manager.downloadUpdate();
    expect(manager.getState().status).toBe("ready_to_install");
    return { manager, openPath, appAdapter };
  }

  it("errors when no installer file has been downloaded", async () => {
    const { manager } = makeMocks();
    const state = await manager.installUpdate();
    expect(state.status).toBe("error");
    expect(state.error).toMatch(/Installer file missing/);
  });

  it("Linux AppImage: transitions to ready_to_restart without spawning/openPath", async () => {
    const { manager, openPath } = await installViaDownload("linux", "aic.AppImage");

    const state = await manager.installUpdate();

    expect(state.status).toBe("ready_to_restart");
    expect(openPath).not.toHaveBeenCalled();
  });

  it("macOS: opens the staged installer via shell.openPath", async () => {
    const { manager, openPath } = await installViaDownload("darwin", "aic.dmg");

    const state = await manager.installUpdate();

    expect(state.status).toBe("ready_to_restart");
    expect(openPath).toHaveBeenCalledTimes(1);
    expect((openPath.mock.calls[0][0] as string).endsWith("aic.dmg")).toBe(true);
  });

  it("macOS: surfaces an error when shell.openPath fails", async () => {
    setPlatform("darwin");
    const { manager, openPath } = await installViaDownload("darwin", "aic.dmg");
    vi.mocked(openPath).mockResolvedValue("No application handles this file");

    const state = await manager.installUpdate();

    expect(state.status).toBe("error");
    expect(state.error).toMatch(/Could not open installer/);
  });
});

describe("UpdateManager constructor compatibility", () => {
  it("still accepts a config object as the first argument (main.ts style)", () => {
    const { manager } = makeMocks();
    const configStyle = new UpdateManager({ autoDownload: false, channel: "beta" });
    expect(configStyle.getConfig().autoDownload).toBe(false);
    expect(configStyle.getConfig().channel).toBe("beta");
    // Keep the injected manager usable too.
    expect(manager.getConfig().channel).toBe("stable");
  });

  it("exposes a serializable state snapshot", async () => {
    const { manager } = makeMocks();
    await manager.checkForUpdates();
    const state: UpdateState = manager.getState();
    expect(state.currentVersion).toBe(CURRENT_VERSION);
    expect(state.baseUrl).toMatch(/^https:/);
  });
});