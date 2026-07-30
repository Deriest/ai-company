# 53 — Update System

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Architecture

```
UpdateManager (main process)
  → manifestUrl() → {baseUrl}/latest.json
  → fetchJson(url) → parseManifest(raw)
  → isNewerVersion(remote, current)
  → If newer: resolve artifact for process.platform
  → downloadFile(artifact.downloadUrl, stagedPath)
  → sha256File(stagedPath) vs artifact.sha256
  → If match: rename temp → final, status = "ready_to_install"
  → installUpdate() → spawn installer
```

## Manifest Schema

**Source:** `src/shared/updateLogic.ts:1-98`

```typescript
type UpdateManifest = {
  version: string;           // "2.0.2"
  channel: string;           // "stable" | "beta" | "dev"
  releaseDate?: string;      // ISO 8601
  releaseNotes?: string;     // Markdown or plain text
  minimumVersion?: string;   // Minimum client version to update
  mandatory?: boolean;       // Force update
  platforms: Partial<Record<PlatformKey, PlatformArtifact>>;
};

type PlatformKey = "win32" | "linux" | "darwin";

type PlatformArtifact = {
  downloadUrl: string;       // Full URL to installer
  sha256: string;            // Expected hash
  size: number;              // File size in bytes
  filename: string;          // Local filename
  type: "nsis" | "portable" | "AppImage" | "deb" | "zip" | "dmg";
};
```

## Configuration

**Source:** `src/shared/updateLogic.ts:63-98`

```typescript
type UpdateConfig = {
  baseUrl: string;           // Default: http://192.168.2.10:8088
  channel: UpdateChannel;    // Default: "stable"
  autoCheck: boolean;        // Default: true
  autoDownload: boolean;     // Default: false
  notifyBeforeInstall: boolean; // Default: true
  lastCheckedAt: string | null;
};
```

## Update States

| State | Description |
|---|---|
| `idle` | No update activity |
| `checking` | Fetching manifest |
| `available` | Newer version found |
| `up_to_date` | Current version is latest |
| `downloading` | Downloading artifact |
| `verifying` | SHA256 verification in progress |
| `ready_to_install` | Verified, ready to launch installer |
| `installing` | Installer launched |
| `error` | Any failure |

## Version Comparison

**Source:** `src/shared/updateLogic.ts:25-50`

- Parse: `v2.0.2` → `[2, 0, 2]`
- Compare: left-to-right, first differing segment wins
- `2.0.2 > 2.0.1` → true
- `2.0.2 > 2.1.0` → false

## Platform Detection

- `process.platform === "win32"` → key `"win32"`
- `process.platform === "linux"` → key `"linux"`
- `process.platform === "darwin"` → key `"darwin"`

## Default URLs

| Environment | URL |
|---|---|
| Local dev | `http://192.168.2.10:8088` |
| Production | `https://download.aicompany.biz.id` |
| Override | `AIC_UPDATE_BASE_URL` env var |

## Issues

1. **Default URL is hardcoded to LAN IP** — `http://192.168.2.10:8088` only works on the local network. Must be configurable per installation.
2. **No code signing** — artifacts are verified by SHA256 but not cryptographically signed. Users must trust the download source.
3. **Windows-only installer tested** — NSIS works; Linux AppImage/deb untested in auto-update flow.
4. **No rollback** — if update fails after install, user must manually reinstall previous version.
5. **Manifest field names inconsistent** — v1.0.8 expected `downloadUrl` in a specific structure; current code expects `PlatformArtifact` type. Need to ensure backward compatibility.
