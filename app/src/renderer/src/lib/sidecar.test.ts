import { describe, it, expect } from "vitest";
import path from "node:path";

/**
 * Mirrors production resolvePythonPath priority without Electron app object.
 * Packaged portable runtime MUST win over system python.
 */
function resolvePythonPathLogic(opts: {
  platform: "win32" | "linux";
  isPackaged: boolean;
  resourcesPath?: string;
  packagingRoot?: string;
  platformDir: string;
  exists: (p: string) => boolean;
}): string | null {
  const { platform, isPackaged, resourcesPath, packagingRoot, platformDir, exists } = opts;
  const isWin = platform === "win32";
  const candidates: string[] = [];

  if (resourcesPath) {
    if (isWin) candidates.push(path.join(resourcesPath, "python-win", "python.exe"));
    else {
      candidates.push(path.join(resourcesPath, "python-linux", "bin", "python"));
      candidates.push(path.join(resourcesPath, "python-linux", "bin", "python3"));
    }
  }
  if (packagingRoot) {
    if (isWin) candidates.push(path.join(packagingRoot, "python-win", "python.exe"));
    else {
      candidates.push(path.join(packagingRoot, "python-linux", "bin", "python"));
      candidates.push(path.join(packagingRoot, "python-linux", "bin", "python3"));
    }
  }
  if (isWin) {
    candidates.push(path.join(platformDir, ".venv", "Scripts", "python.exe"));
    candidates.push(path.join(platformDir, "venv", "Scripts", "python.exe"));
  } else {
    candidates.push(path.join(platformDir, ".venv", "bin", "python"));
    candidates.push(path.join(platformDir, "venv", "bin", "python"));
  }
  if (!isPackaged) {
    if (!isWin) candidates.push("/usr/bin/python3");
    candidates.push(isWin ? "python.exe" : "python3");
    candidates.push("python");
  }

  for (const c of candidates) {
    if (!c) continue;
    if (!path.isAbsolute(c) && !c.includes(path.sep) && !c.includes("/") && !c.includes("\\")) {
      return c;
    }
    if (exists(c)) return c;
  }
  return null;
}

describe("Sidecar Runtime Resolution", () => {
  it("prefers packaged Windows python.exe over system python", () => {
    const resources = "/app/resources";
    const py = resolvePythonPathLogic({
      platform: "win32",
      isPackaged: true,
      resourcesPath: resources,
      platformDir: "/app/resources/backend",
      exists: (p) => p === path.join(resources, "python-win", "python.exe"),
    });
    expect(py).toBe(path.join(resources, "python-win", "python.exe"));
  });

  it("prefers packaged Linux python-linux over system python3", () => {
    const resources = "/app/resources";
    const py = resolvePythonPathLogic({
      platform: "linux",
      isPackaged: true,
      resourcesPath: resources,
      platformDir: "/app/resources/backend",
      exists: (p) => p === path.join(resources, "python-linux", "bin", "python"),
    });
    expect(py).toBe(path.join(resources, "python-linux", "bin", "python"));
  });

  it("falls back to platform .venv in development", () => {
    const dir = "/home/tvd/AI-Company/backend";
    const py = resolvePythonPathLogic({
      platform: "linux",
      isPackaged: false,
      platformDir: dir,
      exists: (p) => p === `${dir}/.venv/bin/python`,
    });
    expect(py).toBe(`${dir}/.venv/bin/python`);
  });

  it("returns null when packaged and no bundled runtime exists", () => {
    const py = resolvePythonPathLogic({
      platform: "win32",
      isPackaged: true,
      resourcesPath: "/app/resources",
      platformDir: "/app/resources/backend",
      exists: () => false,
    });
    expect(py).toBeNull();
  });

  it("does not use system python in packaged mode", () => {
    const py = resolvePythonPathLogic({
      platform: "linux",
      isPackaged: true,
      resourcesPath: "/app/resources",
      platformDir: "/app/resources/backend",
      exists: (p) => p === "/usr/bin/python3",
    });
    expect(py).toBeNull();
  });
});
