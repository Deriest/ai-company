/** Pure update helpers — no Electron dependency (safe for unit tests). */

export type UpdateChannel = "stable" | "beta" | "dev";

export type PlatformKey = "win32" | "linux" | "darwin";

export type PlatformArtifact = {
  downloadUrl: string;
  sha256: string;
  size: number;
  filename: string;
  type: "nsis" | "portable" | "AppImage" | "deb" | "zip" | "dmg";
};

export type UpdateManifest = {
  version: string;
  channel: UpdateChannel | string;
  releaseDate?: string;
  releaseNotes?: string;
  minimumVersion?: string;
  mandatory?: boolean;
  platforms: Partial<Record<PlatformKey, PlatformArtifact>>;
};

export function parseVersion(v: string): number[] {
  const s = String(v || "0").replace(/^v/i, "");
  const parts = s.split(/[.+-]/);
  const result: number[] = [];
  for (const p of parts) {
    const num = parseInt(p.replace(/\D/g, ""), 10) || 0;
    result.push(num);
    const alpha = p.replace(/\d/g, "").toLowerCase();
    if (alpha) {
      for (let i = 0; i < alpha.length; i++) {
        result.push(alpha.charCodeAt(i) - 96);
      }
    }
  }
  return result.length ? result : [0];
}

/** Returns true if remote > local. */
export function isNewerVersion(remote: string, local: string): boolean {
  const a = parseVersion(remote);
  const b = parseVersion(local);
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i] || 0;
    const y = b[i] || 0;
    if (x > y) return true;
    if (x < y) return false;
  }
  return false;
}

export function compareVersions(a: string, b: string): number {
  if (isNewerVersion(a, b)) return 1;
  if (isNewerVersion(b, a)) return -1;
  return 0;
}

export function parseManifest(raw: unknown): UpdateManifest {
  if (!raw || typeof raw !== "object") throw new Error("Invalid manifest: not an object");
  const o = raw as Record<string, unknown>;
  if (!o.version || typeof o.version !== "string") throw new Error("Invalid manifest: missing version");
  if (!o.platforms || typeof o.platforms !== "object") throw new Error("Invalid manifest: missing platforms");
  return o as unknown as UpdateManifest;
}

export const DEFAULT_UPDATE_BASE_URL = "http://192.168.2.10:8088";
export const PUBLIC_UPDATE_BASE_URL = "https://download.aicompany.biz.id";

export type UpdateConfig = {
  baseUrl: string;
  channel: UpdateChannel;
  autoCheck: boolean;
  autoDownload: boolean;
  notifyBeforeInstall: boolean;
  lastCheckedAt: string | null;
};

export function resolveUpdateBaseUrl(
  stored?: string | null,
  env?: Record<string, string | undefined>
): string {
  const fromEnv = env?.AIC_UPDATE_BASE_URL || env?.AIC_DOWNLOAD_BASE_URL;
  if (fromEnv && fromEnv.trim()) return fromEnv.trim().replace(/\/$/, "");
  if (stored && stored.trim()) return stored.trim().replace(/\/$/, "");
  return DEFAULT_UPDATE_BASE_URL;
}

export function manifestUrl(baseUrl: string, channel: UpdateChannel = "stable"): string {
  const base = baseUrl.replace(/\/$/, "");
  if (channel === "stable") return `${base}/latest.json`;
  return `${base}/latest-${channel}.json`;
}

export function defaultUpdateConfig(partial?: Partial<UpdateConfig>): UpdateConfig {
  return {
    baseUrl: DEFAULT_UPDATE_BASE_URL,
    channel: "stable",
    autoCheck: true,
    autoDownload: false,
    notifyBeforeInstall: true,
    lastCheckedAt: null,
    ...partial,
  };
}
