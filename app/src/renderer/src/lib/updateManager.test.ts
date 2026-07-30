import { describe, it, expect } from "vitest";
import {
  isNewerVersion,
  compareVersions,
  parseManifest,
  resolveUpdateBaseUrl,
  manifestUrl,
  defaultUpdateConfig,
  DEFAULT_UPDATE_BASE_URL,
} from "../../../shared/updateLogic";

describe("isNewerVersion", () => {
  it("detects newer patch", () => {
    expect(isNewerVersion("1.0.1", "1.0.0")).toBe(true);
  });
  it("same is not newer", () => {
    expect(isNewerVersion("1.0.0", "1.0.0")).toBe(false);
  });
  it("older is not newer", () => {
    expect(isNewerVersion("1.0.0", "1.0.1")).toBe(false);
  });
  it("handles v prefix", () => {
    expect(isNewerVersion("v1.2.0", "1.1.9")).toBe(true);
  });
});

describe("compareVersions", () => {
  it("orders correctly", () => {
    expect(compareVersions("1.0.1", "1.0.0")).toBe(1);
    expect(compareVersions("1.0.0", "1.0.1")).toBe(-1);
    expect(compareVersions("1.0.0", "1.0.0")).toBe(0);
  });
});

describe("parseManifest", () => {
  it("accepts valid manifest", () => {
    const m = parseManifest({
      version: "1.0.1",
      channel: "stable",
      platforms: {
        win32: {
          downloadUrl: "http://x/Setup.exe",
          sha256: "abc",
          size: 1,
          filename: "Setup.exe",
          type: "nsis",
        },
      },
    });
    expect(m.version).toBe("1.0.1");
    expect(m.platforms.win32?.filename).toBe("Setup.exe");
  });
  it("rejects missing version", () => {
    expect(() => parseManifest({ platforms: {} })).toThrow(/version/i);
  });
});

describe("updateConfig", () => {
  it("defaults to LAN base", () => {
    expect(resolveUpdateBaseUrl(null, {})).toBe(DEFAULT_UPDATE_BASE_URL);
  });
  it("env overrides", () => {
    expect(resolveUpdateBaseUrl(null, { AIC_UPDATE_BASE_URL: "https://download.aicompany.biz.id/" })).toBe(
      "https://download.aicompany.biz.id"
    );
  });
  it("manifest url stable", () => {
    expect(manifestUrl("http://192.168.2.10:8088", "stable")).toBe("http://192.168.2.10:8088/latest.json");
  });
  it("default config", () => {
    const c = defaultUpdateConfig();
    expect(c.autoCheck).toBe(true);
    expect(c.channel).toBe("stable");
  });
});
