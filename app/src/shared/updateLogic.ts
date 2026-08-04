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
  const s = String(v || "0").replace(/^v/i, "").split("+")[0];
  const [base, pre] = s.split("-", 2);
  const core = base.split(".").map((p) => parseInt(p, 10) || 0);
  while (core.length < 3) core.push(0);
  if (!pre) return core;
  const preParts: number[] = [];
  for (const p of pre.split(".")) {
    const num = parseInt(p, 10);
    if (Number.isNaN(num)) {
      for (let i = 0; i < p.length; i++) preParts.push(p.charCodeAt(i) - 96);
    } else {
      preParts.push(num);
    }
  }
  // Keep ALL core components (no truncation to 3 parts) so 4-part
  // versions are compared on the same padding rule as 3-part ones.
  return [...core, -1, ...preParts];
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
  const platforms = o.platforms as Record<string, unknown>;
  for (const [key, val] of Object.entries(platforms)) {
    if (!val || typeof val !== "object") {
      throw new Error(`Invalid manifest: platform "${key}" is not an object`);
    }
    const art = val as Record<string, unknown>;
    // sha256 is REQUIRED — checksum verification must never be skipped.
    for (const field of ["sha256", "filename", "downloadUrl"] as const) {
      if (typeof art[field] !== "string" || !art[field]) {
        throw new Error(`Invalid manifest: platform "${key}" missing ${field}`);
      }
    }
  }
  return o as unknown as UpdateManifest;
}

export const DEFAULT_UPDATE_BASE_URL = "https://raw.githubusercontent.com/Deriest/ai-company/main";
export const PUBLIC_UPDATE_BASE_URL = "https://raw.githubusercontent.com/Deriest/ai-company/main";

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
  const candidate = (fromEnv && fromEnv.trim()) || (stored && stored.trim()) || DEFAULT_UPDATE_BASE_URL;
  return validateUpdateBaseUrl(candidate.trim().replace(/\/$/, ""));
}

/**
 * Require https:// for update sources. Only http://127.0.0.1 is allowed
 * for local development mirrors. Throws for anything else (http, file, ftp).
 */
export function validateUpdateBaseUrl(url: string): string {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    throw new Error(`Invalid update base URL: ${url}`);
  }
  const isLocal = u.protocol === "http:" && u.hostname === "127.0.0.1";
  const isHttps = u.protocol === "https:";
  if (!isLocal && !isHttps) {
    throw new Error("Update base URL must use https:// (or http://127.0.0.1 for local dev)");
  }
  return url.replace(/\/$/, "");
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
