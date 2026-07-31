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

function fetchJson(url: string, timeoutMs = 30000): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https") ? https : http;
    const req = lib.get(url, { timeout: timeoutMs }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        fetchJson(res.headers.location, timeoutMs).then(resolve, reject);
        return;
      }
      if ((res.statusCode || 0) >= 400) {
        reject(new Error(`HTTP ${res.statusCode} fetching ${url}`));
        res.resume();
        return;
      }
      const chunks: Buffer[] = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
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
  onProgress?: (downloaded: number, total: number, speed: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https") ? https : http;
    const file = fs.createWriteStream(dest);
    const started = Date.now();
    let downloaded = 0;

    const req = lib.get(url, { timeout: 120000 }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        fs.unlink(dest, () => {
          downloadFile(res.headers.location!, dest, onProgress).then(resolve, reject);
        });
        return;
      }
      if ((res.statusCode || 0) >= 400) {
        file.close();
        fs.unlink(dest, () => reject(new Error(`HTTP ${res.statusCode} downloading ${url}`)));
        res.resume();
        return;
      }
      const total = parseInt(String(res.headers["content-length"] || "0"), 10) || 0;
      res.on("data", (chunk: Buffer) => {
        downloaded += chunk.length;
        const elapsed = Math.max((Date.now() - started) / 1000, 0.001);
        onProgress?.(downloaded, total, downloaded / elapsed);
      });
      res.pipe(file);
      file.on("finish", () => file.close(() => resolve()));
    });
    req.on("error", (err) => {
      file.close();
      fs.unlink(dest, () => reject(err));
    });
    req.on("timeout", () => {
      req.destroy();
      file.close();
      fs.unlink(dest, () => reject(new Error("Download timeout")));
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
    this.config = { ...this.config, ...partial };
    if (partial.baseUrl !== undefined) {
      this.config.baseUrl = resolveUpdateBaseUrl(partial.baseUrl, process.env as Record<string, string | undefined>);
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
    if (this.checking) return this.getState();
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
          availableVersion: manifest.version,
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
    const artifact = this.state.artifact;
    if (!artifact) {
      this.setState({ status: "error", error: "No update artifact selected. Check for updates first." });
      return this.getState();
    }
    this.abortDownload = false;
    const dir = path.join(app.getPath("userData"), "aic-ade", "updates", "staged");
    fs.mkdirSync(dir, { recursive: true });
    const tempDest = path.join(dir, `${artifact.filename || `update-${this.state.availableVersion}`}.tmp`);
    const finalDest = path.join(dir, artifact.filename || `update-${this.state.availableVersion}`);
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
      if (expected && hash.toLowerCase() !== expected) {
        fs.unlinkSync(tempDest);
        this.setState({
          status: "error",
          error: `SHA256 mismatch. Expected ${expected.slice(0, 16)}… got ${hash.slice(0, 16)}…`,
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
