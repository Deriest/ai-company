/**
 * AIC ADE UpdateManager — production-quality async desktop updater.
 *
 * Architecture:
 *   UpdateManager → Manifest → Downloader → Verifier → Installer → Restart
 *
 * All network I/O is async and never blocks app startup.
 */

import { app, shell, Notification } from "electron";
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
  isMandatoryUpdate,
  parseManifest,
} from "../shared/updateLogic";
import { verifyManifestSignature, getVerificationStatus } from "../shared/updateSecurity";

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
  | "ready_to_restart"
  | "installing"
  | "error";

export type UpdateState = {
  status: UpdateStatus;
  currentVersion: string;
  availableVersion?: string;
  releaseNotes?: string;
  mandatory?: boolean;
  notifyBeforeInstall?: boolean;
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

/** Network/disk I/O seam — injected so tests can run without network or real files. */
export type IO = {
  fetchJson: (url: string, timeoutMs?: number) => Promise<unknown>;
  downloadFile: (
    url: string,
    dest: string,
    onProgress?: (downloaded: number, total: number, speed: number) => void
  ) => Promise<void>;
  sha256File: (filePath: string) => Promise<string>;
};

/** Electron surface used by the updater — injected so tests avoid real Electron. */
export type AppAdapter = {
  getVersion: () => string;
  getPath: (name: "userData") => string;
  shell: {
    openPath: (path: string) => Promise<string>;
    openExternal?: (url: string) => Promise<void>;
  };
  Notification: {
    isSupported: () => boolean;
    new (opts: { title: string; body: string }): { show: () => void };
  };
  exit?: (code?: number) => void;
  quit?: () => void;
  relaunch?: () => void;
};

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

/**
 * QA-SEC: the staged installer filename comes from an unsigned manifest. Return
 * the basename only if it avoids path separators, shell metacharacters, and
 * control/whitespace characters. Spaces are allowed (legit names like
 * "AIC ADE Setup-win64.exe" are staged with spaces and are safe in the argv/
 * joined-path forms used at install). Returns null so callers can reject.
 */
function sanitizeStagedFilename(file: string): string | null {
  const base = path.basename(file);
  return /^[A-Za-z0-9._ -]+$/.test(base) ? base : null;
}

export class UpdateManager {
  private state: UpdateState;
  private listeners = new Set<UpdateListener>();
  private config: UpdateConfig;
  private io: IO;
  private appAdapter: AppAdapter;
  private checking = false;
  private downloading = false;
  private abortDownload = false;
  private _backendProc: any = null;

  setBackendProc(proc: any) { this._backendProc = proc; }

  /**
   * @param config     Update configuration (the historical first argument,
   *                   still used by main.ts).
   * @param io         Optional I/O seam — falls back to the real fetchJson /
   *                   downloadFile / sha256File implementations.
   * @param appAdapter Optional Electron seam — falls back to real electron.
   *                   When the first argument itself looks like an IO object
   *                   (i.e. has fetchJson/downloadFile/sha256File), it is
   *                   treated as the io seam and the second as appAdapter,
   *                   preserving the `new UpdateManager(io, appAdapter)`
   *                   injection style.
   */
  constructor(
    config?: Partial<UpdateConfig> | Partial<IO>,
    io?: Partial<IO> | Partial<AppAdapter>,
    appAdapter?: Partial<AppAdapter>
  ) {
    const isIoShape = (v: unknown): v is Partial<IO> =>
      !!v && typeof v === "object" && ("fetchJson" in v || "downloadFile" in v || "sha256File" in v);
    let cfg = config;
    let ioOpts: Partial<IO> | undefined;
    let adapterOpts = appAdapter;
    if (isIoShape(cfg)) {
      adapterOpts = io as Partial<AppAdapter> | undefined;
      ioOpts = cfg;
      cfg = undefined;
    } else {
      ioOpts = io as Partial<IO> | undefined;
    }
    this.config = defaultUpdateConfig(cfg);
    this.io = {
      fetchJson: ioOpts?.fetchJson ?? fetchJson,
      downloadFile: ioOpts?.downloadFile ?? downloadFile,
      sha256File: ioOpts?.sha256File ?? sha256File,
    };
    this.appAdapter = {
      getVersion: adapterOpts?.getVersion ?? (() => app.getVersion()),
      getPath: adapterOpts?.getPath ?? ((name) => app.getPath(name)),
      shell: adapterOpts?.shell ?? shell,
      Notification: adapterOpts?.Notification ?? Notification,
      exit: adapterOpts?.exit ?? ((code) => app.exit(code)),
      quit: adapterOpts?.quit ?? (() => app.quit()),
      relaunch: adapterOpts?.relaunch ?? (() => app.relaunch()),
    };
    this.state = {
      status: "idle",
      currentVersion: this.appAdapter.getVersion(),
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

  /** Native notification shown before an auto-download when notifyBeforeInstall is on. */
  private notifyUpdateAvailable(): void {
    try {
      if (!this.appAdapter.Notification.isSupported()) return;
      const n = new this.appAdapter.Notification({
        title: "Update available",
        body: `AIC ADE ${this.state.availableVersion ?? ""} is ready to download. Open Settings → Updates to install it.`,
      });
      n.show();
    } catch {
      /* ignore */
    }
  }

  async checkForUpdates(_opts?: { silent?: boolean }): Promise<UpdateState> {
    if (this.checking || this.downloading) return this.getState();
    this.checking = true;
    this.setState({ status: "checking", error: undefined });
    try {
      const url = manifestUrl(this.config.baseUrl, this.config.channel);
      
      // Fetch manifest + signature side-by-side. The manifest MUST go through
      // the injected io.fetchJson seam (so tests can mock it) — and through the
      // hardened transport (https-only, size cap, redirect cap). The raw
      // global `fetch` previously used here bypassed both, which is why the
      // injected seam never took effect and the transport guardrails were dead.
      const raw = await this.io.fetchJson(url);
      const signature = await requestRaw(`${url}.sig`, 30000, MAX_MANIFEST_BYTES, "signature")
        .then((v) => String(v))
        .catch(() => "");
      
      // Verify cryptographic signature before parsing — C2 FIX: enforce in
      // packaged builds (Packaged Electron does not reliably set NODE_ENV,
      // so pass app.isPackaged explicitly).
      const _isPackaged = (() => {
        try {
          return (app as unknown as { isPackaged?: boolean })?.isPackaged ?? undefined;
        } catch {
          return undefined;
        }
      })();
      if (signature) {
        const sigValid = verifyManifestSignature(raw, signature, _isPackaged);
        if (!sigValid) {
          throw new Error("Manifest signature verification failed - possible MITM attack");
        }
      } else {
        // No signature provided — fatal in packaged builds (fail-closed)
        const sigValid = verifyManifestSignature(raw, "", _isPackaged);
        if (!sigValid) {
          throw new Error("Manifest signature verification failed — packaged build requires a signed manifest");
        }
        const status = getVerificationStatus();
        if (status.nodeEnv === "production") {
          console.warn(
            "[UpdateManager] Manifest served without signature - deployment misconfigured"
          );
        }
      }
      
      const manifest = parseManifest(raw);
      const now = new Date().toISOString();
      this.config.lastCheckedAt = now;

      const platform = process.platform as PlatformKey;
      const artifact = manifest.platforms[platform];
      const newer = isNewerVersion(manifest.version, this.appAdapter.getVersion());

      if (!newer) {
        this.setState({
          status: "up_to_date",
          availableVersion: undefined,
          lastCheckedAt: now,
          releaseNotes: manifest.releaseNotes,
          mandatory: isMandatoryUpdate(manifest, this.appAdapter.getVersion()),
          artifact: undefined,
          dismissedVersion: undefined,
          notifyBeforeInstall: false,
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
          mandatory: isMandatoryUpdate(manifest, this.appAdapter.getVersion()),
          artifact: art,
          lastCheckedAt: now,
        });
        return this.getState();
      }

      this.setState({
        status: "available",
        availableVersion: manifest.version,
        releaseNotes: manifest.releaseNotes,
        mandatory: isMandatoryUpdate(manifest, this.appAdapter.getVersion()),
        artifact: art,
        lastCheckedAt: now,
        dismissedVersion: undefined,
        notifyBeforeInstall: false,
      });

      if (this.config.autoDownload) {
        if (this.config.notifyBeforeInstall) {
          // Ask before downloading — surface a notification instead of
          // silently pulling the artifact.
          this.setState({ notifyBeforeInstall: true });
          this.notifyUpdateAvailable();
        } else {
          this.checking = false;
          void this.downloadUpdate();
        }
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
      const dir = path.join(this.appAdapter.getPath("userData"), "aic-ade", "updates", "staged");
      fs.mkdirSync(dir, { recursive: true });
      // QA-SEC: sanitize artifact filename — path.basename() blocks "../"
      // traversal escapes, and the shared sanitizer (same one used at install)
      // rejects shell metacharacters. Fall back to a guaranteed-safe name if the
      // manifest filename is rejected outright so a bad name is never staged.
      const rawFilename = path.basename(artifact.filename || `update-${this.state.availableVersion}`);
      const safeFilename =
        sanitizeStagedFilename(rawFilename) ||
        sanitizeStagedFilename(`update-${this.state.availableVersion}`) ||
        "update";
      const tempDest = path.join(dir, `${safeFilename}.tmp`);
      const finalDest = path.join(dir, safeFilename);
      this.setState({
        status: "downloading",
        progress: 0,
        bytesDownloaded: 0,
        bytesTotal: artifact.size || 0,
        downloadPath: tempDest,
        error: undefined,
        notifyBeforeInstall: false,
      });

      try {
        await this.io.downloadFile(artifact.downloadUrl, tempDest, (downloaded, total, speed) => {
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

        // M5: enforce the manifest-declared size before trusting the file.
        // SHA256 below is the real integrity gate, but a size mismatch is a
        // cheap early reject (truncated download, wrong asset, or a manifest
        // whose `size` disagrees with the served bytes) — fail here instead of
        // hashing a bogus file.
        if (artifact.size && artifact.size > 0) {
          let actualSize = 0;
          try {
            actualSize = fs.statSync(tempDest).size;
          } catch {
            actualSize = 0;
          }
          if (actualSize !== artifact.size) {
            try { fs.unlinkSync(tempDest); } catch { /* best effort */ }
            this.setState({
              status: "error",
              error: `Downloaded size ${actualSize} bytes does not match manifest size ${artifact.size} bytes`,
              downloadPath: undefined,
            });
            return this.getState();
          }
        }

        const hash = await this.io.sha256File(tempDest);
        const expected = (artifact.sha256 || "").toLowerCase();
        // sha256 is REQUIRED by parseManifest — never skip verification.
        // Ensure both hashes are compared in lowercase to avoid case-sensitivity issues.
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
      if (process.platform === "darwin") {
        // macOS: surface the .dmg to the user (Finder opens it). The restart
        // is applied separately via quitAndInstall so the freshly installed
        // app takes effect.
        const err = await this.appAdapter.shell.openPath(file);
        if (err) {
          this.setState({ status: "error", error: `Could not open installer: ${err}` });
          return this.getState();
        }
      }
      // win32 / linux AppImage: do NOT spawn the installer here — quitAndInstall
      // performs the actual install + relaunch. Spawning now would either run
      // the new AppImage while we still hold the single-instance lock (it quits
      // and focuses the old window — a silent no-op) or double-install on
      // Windows (installer opens here, then quitAndInstall runs it again).
      this.setState({ status: "ready_to_restart" });
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
      // QA-SEC: the staged filename comes from an unsigned manifest — reject any
      // filename outside the safe charset before it is interpolated into the
      // batch script (Cmd.exe would otherwise evaluate shell metacharacters).
      const safeBase = sanitizeStagedFilename(file);
      if (!safeBase) {
        this.setState({ status: "error", error: "Installer filename rejected (unsafe)." });
        return;
      }
      // Write a temp batch script that waits 2s then runs installer
      const batFile = file + '.update.bat';
      fs.writeFileSync(batFile, `@echo off\r\ntimeout /t 2 /nobreak >nul\r\nstart "AIC ADE Update" "${path.join(path.dirname(file), safeBase)}"\r\ndel "%~f0"\r\n`);
      spawn('cmd', ['/c', batFile], { detached: true, stdio: 'ignore' }).unref();
      // Exit immediately so installer can overwrite files
      setImmediate(() => this.appAdapter.exit?.(0));
    } else if (process.platform === "linux" && file.endsWith(".AppImage")) {
      // QA-SEC: validate the filename, then spawn the AppImage directly (no
      // `sh -c` string interpolation) so shell metacharacters in a malicious
      // filename can never be evaluated.
      const safeBase = sanitizeStagedFilename(file);
      if (!safeBase) {
        this.setState({ status: "error", error: "Installer filename rejected (unsafe)." });
        return;
      }
      try { fs.chmodSync(file, 0o755); } catch {}
      // Run after a short delay (same behaviour as the previous `sleep 2 &&`).
      spawn('sh', ['-c', 'sleep 2 && exec "$1"', 'aic-update', file], { detached: true, stdio: 'ignore' }).unref();
      // Let the new AppImage take over — quit gracefully so the backend is
      // torn down via the normal will-quit path.
      setImmediate(() => this.appAdapter.quit?.());
    } else {
      // macOS: never spawn the .dmg as a binary (that fails with
      // EXEC_BAD_ACCESS). Open the staged .dmg in Finder (no-op if already
      // mounted) then relaunch so the freshly installed app takes effect.
      void this.appAdapter.shell.openPath(file).then(() => {
        this.appAdapter.relaunch?.();
        this.appAdapter.exit?.(0);
      });
    }
  }

  dismiss(): void {
    const allowed: UpdateStatus[] = ["available", "ready_to_install", "ready_to_restart", "up_to_date", "error"];
    // Mandatory updates cannot be dismissed — only install/quit-and-install is allowed.
    if (this.state.mandatory && (this.state.status === "available" || this.state.status === "ready_to_install" || this.state.status === "ready_to_restart")) {
      return;
    }
    if (allowed.includes(this.state.status)) {
      this.setState({
        status: "idle",
        error: undefined,
        dismissedVersion: this.state.availableVersion || this.state.dismissedVersion,
      });
    }
  }
}
