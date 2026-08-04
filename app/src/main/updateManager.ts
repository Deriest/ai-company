/**
 * AIC ADE UpdateManager — production-quality async desktop updater.
 *
 * Architecture:
 *   UpdateManager → Manifest → Downloader → Verifier → Installer → Restart
 *
 * All network I/O is async and never blocks app startup.
 */

import { app, shell } from "electron";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import http from "node:http";
import https from "node:https";
import { spawn } from "node:child_process";
import {
  type UpdateChannel,
  type UpdateConfig,
  type UpdateManifest,
  type PlatformKey,
  type PlatformArtifact,
  defaultUpdateConfig,
  manifestUrl,
  resolveUpdateBaseUrl,
  isNewerVersion,
  parseManifest,
} from "../shared/updateLogic";

export type {
  UpdateChannel,
  UpdateConfig,
  UpdateManifest,
  PlatformKey,
  PlatformArtifact,
};
export { isNewerVersion, compareVersions, parseManifest } from "../shared/updateLogic";

export type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "up_to_date"
  | "downloading"
  | "verifying"
  | "ready_to_install"
  | "installing"
  | "error";

export type UpdateState = {
  status: UpdateStatus;
  currentVersion: string;
  availableVersion?: string;
  releaseNotes?: string;
  mandatory?: boolean;
  progress?: number;
  bytesDownloaded?: number;
  bytesTotal?: number;
  speedBps?: number;
  error?: string;
  downloadPath?: string;
  lastCheckedAt?: string | null;
  baseUrl: string;
  channel: UpdateChannel;
  artifact?: PlatformArtifact;
  dismissedVersion?: string;
};

export type UpdateListener = (state: UpdateState) => void;

const MAX_REDIRECTS = 5;
const MAX_MANIFEST_BYTES = 1 * 1024 * 1024; // 1MB manifest cap
const MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024; // 8GB artifact safety cap

/** https only (http://127.0.0.1 allowed for local dev mirrors). */
function isAllowedDownloadUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || (u.protocol === "http:" && u.hostname === "127.0.0.1");
  } catch {
    return false;
  }
}

function fetchJson(url: string, timeoutMs = 30000): Promise<unknown> {
  return requestRaw(url, timeoutMs, MAX_MANIFEST_BYTES, "manifest");
}

/**
 * Shared HTTP(S) fetch with hardened transport rules:
 *  - https only (http://127.0.0.1 allowed for local dev mirrors)
 *  - max 5 redirects, https→http downgrades rejected
 *  - response body size cap
 *  - mid-stream errors reject instead of hanging
 */
function requestRaw(
  url: string,
  timeoutMs: number,
  maxBytes: number,
  what: string,
  redirects = 0
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (!isAllowedDownloadUrl(url)) {
      reject(new Error(`Blocked non-HTTPS ${what} URL: ${url}`));
      return;
    }
    if (redirects > MAX_REDIRECTS) {
      reject(new Error(`Too many redirects (${redirects}) fetching ${url}`));
      return;
    }
    const lib = url.startsWith("https") ? https : http;
    let total = 0;
    const req = lib.get(url, { timeout: timeoutMs }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const location = res.headers.location;
        res.resume();
        requestRaw(new URL(location, url).toString(), timeoutMs, maxBytes, what, redirects + 1)
          .then(resolve, reject);
        return;
      }
      if ((res.statusCode || 0) >= 400) {
        reject(new Error(`HTTP ${res.statusCode} fetching ${url}`));
        res.resume();
        return;
      }
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => {
        total += c.length;
        if (total > maxBytes) {
          req.destroy();
          reject(new Error(`${what} too large (>{maxBytes} bytes): ${url}`));
          return;
        }
        chunks.push(c);
      });
      res.on("error", (err) => reject(err));
      res.on("end", () => {
        try {
          const body = Buffer.concat(chunks).toString("utf8");
          resolve(what === "manifest" ? JSON.parse(body) : body);
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error(`Timeout fetching ${url}`));
    });
  });
}

function downloadFile(
  url: string,
  dest: string,
  onProgress?: (downloaded: number, total: number, speed: number) => void,
  redirects = 0
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!isAllowedDownloadUrl(url)) {
      reject(new Error(`Blocked non-HTTPS download URL: ${url}`));
      return;
    }
    if (redirects > MAX_REDIRECTS) {
      reject(new Error(`Too many redirects (${redirects}) downloading ${url}`));
      return;
    }
    const lib = url.startsWith("https") ? https : http;
    const file = fs.createWriteStream(dest);
    const started = Date.now();
    let downloaded = 0;
    let settled = false;

    const fail = (err: Error) => {
      if (settled) return;
      settled = true;
      file.destroy();
      fs.unlink(dest, () => reject(err));
    };

    const req = lib.get(url, { timeout: 120000 }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const location = res.headers.location;
        res.resume();
        file.destroy();
        fs.unlink(dest, () => {
          downloadFile(new URL(location, url).toString(), dest, onProgress, redirects + 1)
            .then(resolve, reject);
        });
        return;
      }
      if ((res.statusCode || 0) >= 400) {
        fail(new Error(`HTTP ${res.statusCode} downloading ${url}`));
        res.resume();
        return;
      }
      const total = parseInt(String(res.headers["content-length"] || "0"), 10) || 0;
      res.on("data", (chunk: Buffer) => {
        downloaded += chunk.length;
        if (downloaded > MAX_DOWNLOAD_BYTES) {
          fail(new Error(`Download exceeds size cap (${MAX_DOWNLOAD_BYTES} bytes): ${url}`));
          req.destroy();
          res.destroy();
          return;
        }
        const elapsed = Math.max((Date.now() - started) / 1000, 0.001);
        onProgress?.(downloaded, total, downloaded / elapsed);
      });
      res.on("error", (err) => fail(err));
      file.on("error", (err) => fail(err));
      res.pipe(file);
      file.on("finish", () => file.close(() => resolve()));
    });
    req.on("error", (err) => fail(err));
    req.on("timeout", () => {
      req.destroy();
      fail(new Error("Download timeout"));
    });
  });
}

export async function sha256File(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("data", (d) => hash.update(d));
    stream.on("end", () => resolve(hash.digest("hex")));
    stream.on("error", reject);
  });
}

export class UpdateManager {
  private state: UpdateState;
  private listeners = new Set<UpdateListener>();
  private config: UpdateConfig;
  private checking = false;
  private downloading = false;
  private abortDownload = false;
  private _backendProc: any = null;

  setBackendProc(proc: any) { this._backendProc = proc; }

  constructor(config?: Partial<UpdateConfig>) {
    this.config = defaultUpdateConfig(config);
    this.state = {
      status: "idle",
      currentVersion: app.getVersion(),
      baseUrl: this.config.baseUrl,
      channel: this.config.channel,
      lastCheckedAt: this.config.lastCheckedAt,
    };
  }

  getState(): UpdateState {
    return { ...this.state };
  }

  getConfig(): UpdateConfig {
    return { ...this.config };
  }

  setConfig(partial: Partial<UpdateConfig>): void {
    const prevBaseUrl = this.config.baseUrl;
    this.config = { ...this.config, ...partial };
    if (partial.baseUrl !== undefined) {
      try {
        this.config.baseUrl = resolveUpdateBaseUrl(partial.baseUrl, process.env as Record<string, string | undefined>);
      } catch (e) {
        // Keep the previous base URL — an invalid value must not be applied.
        this.config.baseUrl = prevBaseUrl;
        throw new Error(e instanceof Error ? e.message : String(e));
      }
    }
    this.state.baseUrl = this.config.baseUrl;
    this.state.channel = this.config.channel;
    this.state.lastCheckedAt = this.config.lastCheckedAt;
    this.emit();
  }

  on(listener: UpdateListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    const snap = this.getState();
    for (const l of this.listeners) {
      try {
        l(snap);
      } catch {
        /* ignore */
      }
    }
  }

  private setState(partial: Partial<UpdateState>): void {
    this.state = { ...this.state, ...partial };
    this.emit();
  }

  async checkForUpdates(_opts?: { silent?: boolean }): Promise<UpdateState> {
    if (this.checking || this.downloading) return this.getState();
    this.checking = true;
    this.setState({ status: "checking", error: undefined });
    try {
      const url = manifestUrl(this.config.baseUrl, this.config.channel);
      const raw = await fetchJson(url);
      const manifest = parseManifest(raw);
      const now = new Date().toISOString();
      this.config.lastCheckedAt = now;

      const platform = process.platform as PlatformKey;
      const artifact = manifest.platforms[platform];
      const newer = isNewerVersion(manifest.version, app.getVersion());

      if (!newer) {
        this.setState({
          status: "up_to_date",
          availableVersion: undefined,
          lastCheckedAt: now,
          releaseNotes: manifest.releaseNotes,
          mandatory: Boolean(manifest.mandatory),
          artifact: undefined,
          dismissedVersion: undefined,
        });
        return this.getState();
      }

      if (!artifact) {
        this.setState({
          status: "error",
          error: `No update package for platform ${platform}`,
          availableVersion: manifest.version,
          lastCheckedAt: now,
        });
        return this.getState();
      }

      // Resolve relative download URLs against base
      const art = { ...artifact };
      if (art.downloadUrl && !/^https?:\/\//i.test(art.downloadUrl)) {
        art.downloadUrl = `${this.config.baseUrl.replace(/\/$/, "")}/${art.downloadUrl.replace(/^\//, "")}`;
      }

      // If this version was already dismissed, don't re-show the banner
      if (manifest.version === this.state.dismissedVersion) {
        this.setState({
          status: "idle",
          availableVersion: manifest.version,
          releaseNotes: manifest.releaseNotes,
          mandatory: Boolean(manifest.mandatory),
          artifact: art,
          lastCheckedAt: now,
        });
        return this.getState();
      }

      this.setState({
        status: "available",
        availableVersion: manifest.version,
        releaseNotes: manifest.releaseNotes,
        mandatory: Boolean(manifest.mandatory),
        artifact: art,
        lastCheckedAt: now,
        dismissedVersion: undefined,
      });

      if (this.config.autoDownload) {
        this.checking = false;
        void this.downloadUpdate();
      }
      return this.getState();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      this.setState({
        status: "error",
        error: `Update check failed: ${msg}`,
        lastCheckedAt: new Date().toISOString(),
      });
      return this.getState();
    } finally {
      this.checking = false;
    }
  }

  async downloadUpdate(): Promise<UpdateState> {
    if (this.downloading) return this.getState();
    this.downloading = true;
    try {
      const artifact = this.state.artifact;
      if (!artifact) {
        this.setState({ status: "error", error: "No update artifact selected. Check for updates first." });
        return this.getState();
      }
      this.abortDownload = false;
      const dir = path.join(app.getPath("userData"), "aic-ade", "updates", "staged");
      fs.mkdirSync(dir, { recursive: true });
      // Sanitize artifact filename — path.basename() blocks "../" traversal escapes.
      const safeFilename = path.basename(artifact.filename || `update-${this.state.availableVersion}`);
      const tempDest = path.join(dir, `${safeFilename}.tmp`);
      const finalDest = path.join(dir, safeFilename);
      this.setState({
        status: "downloading",
        progress: 0,
        bytesDownloaded: 0,
        bytesTotal: artifact.size || 0,
        downloadPath: tempDest,
        error: undefined,
      });

      try {
        await downloadFile(artifact.downloadUrl, tempDest, (downloaded, total, speed) => {
          if (this.abortDownload) return;
          this.setState({
            status: "downloading",
            progress: total ? Math.min(100, Math.round((downloaded / total) * 100)) : undefined,
            bytesDownloaded: downloaded,
            bytesTotal: total || artifact.size,
            speedBps: speed,
          });
        });

        this.setState({ status: "verifying", progress: 100 });
        const hash = await sha256File(tempDest);
        const expected = (artifact.sha256 || "").toLowerCase();
        // sha256 is REQUIRED by parseManifest — never skip verification.
        if (!expected || hash.toLowerCase() !== expected) {
          fs.unlinkSync(tempDest);
          this.setState({
            status: "error",
            error: expected
              ? `SHA256 mismatch. Expected ${expected.slice(0, 16)}… got ${hash.slice(0, 16)}…`
              : "SHA256 verification failed: manifest did not provide a checksum",
            downloadPath: undefined,
          });
          return this.getState();
        }

        // Atomic rename from temp to final staged path
        if (fs.existsSync(finalDest)) {
          fs.unlinkSync(finalDest);
        }
        fs.renameSync(tempDest, finalDest);

        this.setState({
          status: "ready_to_install",
          downloadPath: finalDest,
          progress: 100,
        });
        return this.getState();
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        this.setState({ status: "error", error: `Download failed: ${msg}` });
        return this.getState();
      }
    } finally {
      this.downloading = false;
    }
  }

  async installUpdate(): Promise<UpdateState> {
    const file = this.state.downloadPath;
    if (!file || !fs.existsSync(file)) {
      this.setState({ status: "error", error: "Installer file missing. Download the update first." });
      return this.getState();
    }
    this.setState({ status: "installing" });
    try {
      if (process.platform === "linux" && file.endsWith(".AppImage")) {
        try { fs.chmodSync(file, 0o755); } catch { /* ignore */ }
        spawn(file, [], { detached: true, stdio: "ignore" }).unref();
      } else {
        await shell.openPath(file);
      }
      this.setState({ status: "installing" });
      return this.getState();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      this.setState({ status: "error", error: `Install failed: ${msg}` });
      return this.getState();
    }
  }

  quitAndInstall(): void {
    try {
      if (this._backendProc) this._backendProc.kill("SIGTERM");
    } catch {}
    
    const file = this.state.downloadPath;
    if (!file || !fs.existsSync(file)) {
      this.setState({ status: "error", error: "Installer file missing. Download the update first." });
      return;
    }

    if (process.platform === "win32") {
      // Write a temp batch script that waits 2s then runs installer
      const batFile = file + '.update.bat';
      fs.writeFileSync(batFile, `@echo off\r\ntimeout /t 2 /nobreak >nul\r\nstart "AIC ADE Update" "${file}"\r\ndel "%~f0"\r\n`);
      spawn('cmd', ['/c', batFile], { detached: true, stdio: 'ignore' }).unref();
    } else if (process.platform === "linux" && file.endsWith(".AppImage")) {
      try { fs.chmodSync(file, 0o755); } catch {}
      const cmd = `sleep 2 && "${file}"`;
      spawn('sh', ['-c', cmd], { detached: true, stdio: 'ignore' }).unref();
    } else {
      spawn(file, [], { detached: true, stdio: 'ignore' }).unref();
    }
    
    // Exit immediately so installer can overwrite files
    setImmediate(() => app.exit(0));
  }

  dismiss(): void {
    const allowed: UpdateStatus[] = ["available", "ready_to_install", "up_to_date", "error"];
    if (allowed.includes(this.state.status)) {
      this.setState({
        status: "idle",
        error: undefined,
        dismissedVersion: this.state.availableVersion || this.state.dismissedVersion,
      });
    }
  }
}
