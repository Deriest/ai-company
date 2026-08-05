import { describe, it, expect, afterEach } from "vitest";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { findFreePort, isAllowedNavigation, sanitizeProjectRoot, resolveSafe } from "./security";

const tmpDirs: string[] = [];

function mkTmp(prefix: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tmpDirs.push(dir);
  return dir;
}

afterEach(() => {
  for (const dir of tmpDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

describe("findFreePort", () => {
  it("returns a port that is actually free to bind", async () => {
    const port = await findFreePort(32000, 32999);
    const server = net.createServer();
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, "127.0.0.1", () => resolve());
    });
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it("skips a bound port and resolves a free one", async () => {
    const taken = net.createServer();
    await new Promise<void>((resolve, reject) => {
      taken.once("error", reject);
      taken.listen(0, "127.0.0.1", () => resolve());
    });
    const address = taken.address() as net.AddressInfo;
    const boundPort = address.port;

    const free = await findFreePort(boundPort, boundPort + 10, "127.0.0.1");

    expect(free).not.toBe(boundPort);
    await new Promise<void>((resolve) => taken.close(() => resolve()));
    // The returned port must be bindable.
    const server = net.createServer();
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(free, "127.0.0.1", () => resolve());
    });
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it("rejects when the whole range is exhausted (all ports bound)", async () => {
    const taken = net.createServer();
    await new Promise<void>((resolve, reject) => {
      taken.once("error", reject);
      taken.listen(0, "127.0.0.1", () => resolve());
    });
    const address = taken.address() as net.AddressInfo;
    const boundPort = address.port;

    await expect(findFreePort(boundPort, boundPort, "127.0.0.1")).rejects.toThrow(
      /No free ports in range/
    );
    await new Promise<void>((resolve) => taken.close(() => resolve()));
  });
});

describe("isAllowedNavigation", () => {
  const distDir = path.join(os.tmpdir(), "aic-dist-placeholder");

  it("allows file:// URLs inside dist", () => {
    const url = `file://${distDir}/index.html`;
    expect(isAllowedNavigation(url, distDir, false)).toBe(true);
  });

  it("allows file:// URL equal to the dist dir itself", () => {
    expect(isAllowedNavigation(`file://${distDir}`, distDir, false)).toBe(true);
  });

  it("blocks file:// URLs outside dist", () => {
    expect(isAllowedNavigation("file:///etc/passwd", distDir, false)).toBe(false);
    expect(isAllowedNavigation(`file://${path.join(distDir, "..", "outside.html")}`, distDir, false)).toBe(false);
  });

  it("allows the Vite dev server only when dev is enabled", () => {
    expect(isAllowedNavigation("http://127.0.0.1:5174/", distDir, true)).toBe(true);
    expect(isAllowedNavigation("http://127.0.0.1:5174/index.html", distDir, true)).toBe(true);
    expect(isAllowedNavigation("http://127.0.0.1:5174/", distDir, false)).toBe(false);
  });

  it("blocks external https and http URLs", () => {
    expect(isAllowedNavigation("https://example.com/", distDir, true)).toBe(false);
    expect(isAllowedNavigation("http://example.com/", distDir, true)).toBe(false);
    expect(isAllowedNavigation("http://127.0.0.1:9999/", distDir, true)).toBe(false);
  });

  it("blocks malformed URLs", () => {
    expect(isAllowedNavigation("not a url", distDir, false)).toBe(false);
  });
});

describe("sanitizeProjectRoot", () => {
  it("accepts an existing directory outside system roots", () => {
    const project = path.join(mkTmp("sanitize-ok-"), "myproj");
    fs.mkdirSync(project);
    expect(sanitizeProjectRoot(project, os.homedir(), os.tmpdir())).toBe(project);
  });

  it("rejects system roots (/etc, /)", () => {
    expect(sanitizeProjectRoot("/etc", os.homedir(), os.tmpdir())).toBeNull();
    expect(sanitizeProjectRoot("/", os.homedir(), os.tmpdir())).toBeNull();
  });

  it("rejects home and temp dirs", () => {
    expect(sanitizeProjectRoot(os.homedir(), os.homedir(), os.tmpdir())).toBeNull();
    expect(sanitizeProjectRoot(os.tmpdir(), os.homedir(), os.tmpdir())).toBeNull();
  });

  it("rejects non-existent paths", () => {
    const tmp = mkTmp("sanitize-missing-");
    expect(sanitizeProjectRoot(path.join(tmp, "nope"), os.homedir(), os.tmpdir())).toBeNull();
  });

  it("rejects files (must be a directory)", () => {
    const file = path.join(mkTmp("sanitize-file-"), "f.txt");
    fs.writeFileSync(file, "x");
    expect(sanitizeProjectRoot(file, os.homedir(), os.tmpdir())).toBeNull();
  });

  it("rejects non-string values and empty strings", () => {
    expect(sanitizeProjectRoot(42, os.homedir(), os.tmpdir())).toBeNull();
    expect(sanitizeProjectRoot(null, os.homedir(), os.tmpdir())).toBeNull();
    expect(sanitizeProjectRoot("", os.homedir(), os.tmpdir())).toBeNull();
  });
});

describe("resolveSafe", () => {
  it("allows a path inside the data root", () => {
    const dataRoot = mkTmp("safe-data-");
    const file = path.join(dataRoot, "store", "state.json");
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, "{}");
    expect(resolveSafe(file, [], [dataRoot])).toBe(file);
  });

  it("allows a path inside an extra (project) root even outside the data root", () => {
    const dataRoot = mkTmp("safe-data2-");
    const project = mkTmp("safe-proj-");
    const file = path.join(project, "a.txt");
    fs.writeFileSync(file, "x");
    expect(resolveSafe(file, [project], [dataRoot])).toBe(file);
  });

  it("blocks traversal outside every root", () => {
    const project = mkTmp("safe-proj2-");
    fs.mkdirSync(path.join(project, "sub"));
    expect(() =>
      resolveSafe(path.join(project, "..", "..", "etc", "passwd"), [project], [mkTmp("safe-data3-")])
    ).toThrow(/path not allowed/);
  });

  it("blocks a symlink that resolves outside every root", () => {
    const dataRoot = mkTmp("safe-data4-");
    const project = mkTmp("safe-proj4-");
    const secret = mkTmp("safe-secret-");
    fs.symlinkSync(secret, path.join(project, "link"));
    expect(() =>
      resolveSafe(path.join(project, "link"), [project], [dataRoot])
    ).toThrow(/symlink escape/)
  });

  it("allows a symlink that stays inside the roots", () => {
    const dataRoot = mkTmp("safe-data5-");
    const target = path.join(dataRoot, "inner");
    fs.mkdirSync(target);
    fs.symlinkSync(target, path.join(dataRoot, "link"));
    expect(resolveSafe(path.join(dataRoot, "link"), [], [dataRoot])).toBe(path.join(dataRoot, "link"));
  });
});