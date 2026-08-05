/**
 * Main-process security/network helpers — pure logic + fs/net only (no
 * Electron import), extracted from main.ts so they can be unit-tested in a
 * plain Node vitest environment.
 */

import path from "node:path";
import fs from "node:fs";
import net from "node:net";

/** Reject project-root values that would expand the renderer's file access to the whole machine. */
export const SENSITIVE_FS_ROOTS = new Set([
  "/", "/home", "/root", "/etc", "/usr", "/var", "/tmp", "/bin", "/sbin",
  "/lib", "/lib64", "/proc", "/sys", "/dev", "/boot", "/opt", "/mnt",
  "/media", "/run", "/srv", "/snap", "/nix", "/Volumes", "/System",
  "/Library", "/Private", "/Users", "/Applications", "/Windows",
  "/Program Files", "/Program Files (x86)", "C:\\", "C:\\Windows",
  "C:\\Program Files", "C:\\Program Files (x86)", "C:\\Users",
]);

/**
 * Validate a project-root candidate. Returns the resolved absolute path when
 * it points at an existing directory outside system roots / home / temp,
 * otherwise null. `homePath`/`tempPath` are injected (from app.getPath in the
 * main process) so the helper stays Electron-free.
 */
export function sanitizeProjectRoot(
  value: unknown,
  homePath: string,
  tempPath: string
): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") return null;
  let resolved: string;
  try {
    resolved = path.resolve(value);
  } catch {
    return null;
  }
  const lower = resolved.toLowerCase();
  if (SENSITIVE_FS_ROOTS.has(resolved) || SENSITIVE_FS_ROOTS.has(lower)) return null;
  const home = path.resolve(homePath);
  if (resolved === home || resolved === path.resolve(tempPath)) return null;
  // Must be an existing directory.
  try {
    const st = fs.statSync(resolved);
    if (!st.isDirectory()) return null;
  } catch {
    return null;
  }
  return resolved;
}

/**
 * Resolve a target path and verify it stays inside one of the allowed roots
 * (`dataRoots` = app data dir, plus per-call `extraRoots` such as the project
 * folder). Blocks `..` traversal escapes and, for existing paths, symlinks
 * that point outside the roots.
 */
export function resolveSafe(
  target: string,
  extraRoots: string[] = [],
  dataRoots: string[] = []
): string {
  const resolved = path.resolve(target);
  const roots = [...dataRoots, ...extraRoots].map((r) => path.resolve(r));
  const ok = roots.some((root) => resolved === root || resolved.startsWith(root + path.sep));
  if (!ok) throw new Error(`path not allowed: ${resolved}`);
  // block symlink escape: lstat the resolved path, reject if symlink pointing outside roots
  try {
    const real = fs.realpathSync(resolved);
    if (real !== resolved) {
      const realOk = roots.some((root) => real === root || real.startsWith(root + path.sep));
      if (!realOk) throw new Error(`symlink escape blocked: ${resolved} → ${real}`);
    }
  } catch (e) {
    // path may not exist yet (write case) — only block if it exists and is a symlink
    if (fs.existsSync(resolved)) throw e;
  }
  return resolved;
}

/**
 * Navigation allowlist — only the app's own dist bundle file:// pages and
 * (in dev) the Vite server. M8: arbitrary file:// URLs are rejected; only
 * paths under `distDir` are allowed. `allowDevServer` enables the
 * http://127.0.0.1:5174 exception in development.
 */
export function isAllowedNavigation(
  url: string,
  distDir: string,
  allowDevServer: boolean
): boolean {
  try {
    const u = new URL(url);
    if (u.protocol === "file:") {
      let filePath: string;
      try {
        filePath = path.resolve(decodeURIComponent(u.pathname));
      } catch {
        return false;
      }
      // On Windows, file:///C:/... parses pathname as /C:/... — strip the
      // leading slash before comparing against the resolved dist dir.
      if (/^\/[A-Za-z]:/.test(filePath)) filePath = filePath.slice(1);
      return filePath === distDir || filePath.startsWith(distDir + path.sep);
    }
    if (allowDevServer && u.protocol === "http:" && u.hostname === "127.0.0.1" && u.port === "5174") return true;
    return false;
  } catch {
    return false;
  }
}

/** Find a free TCP port on `host` — try from `start` until one is available. */
export function findFreePort(start: number = 8000, end: number = 8099, host: string = "127.0.0.1"): Promise<number> {
  return new Promise((resolve, reject) => {
    let port = start;
    const tryNext = (): void => {
      if (port > end) {
        reject(new Error(`No free ports in range ${start}-${end}`));
        return;
      }
      const socket = net.createConnection({ host, port });
      socket.setTimeout(300);
      socket.on("connect", () => {
        socket.destroy();
        port++;
        tryNext();
      });
      socket.on("error", () => {
        socket.destroy();
        resolve(port);
      });
      socket.on("timeout", () => {
        socket.destroy();
        resolve(port);
      });
    };
    tryNext();
  });
}