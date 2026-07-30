import { describe, it, expect } from "vitest";
import { detectProjectEnvironment } from "./projectEnv";

describe("detectProjectEnvironment", () => {
  it("detects node", () => {
    const h = detectProjectEnvironment(["package.json", "src", "README.md"]);
    expect(h.kind).toBe("node");
    expect(h.manifests).toContain("package.json");
  });

  it("detects python", () => {
    const h = detectProjectEnvironment(["requirements.txt", "main.py"]);
    expect(h.kind).toBe("python");
  });

  it("detects mixed node+python", () => {
    const h = detectProjectEnvironment(["package.json", "pyproject.toml"]);
    expect(h.kind).toBe("mixed");
  });

  it("unknown when no manifests", () => {
    const h = detectProjectEnvironment(["notes.txt"]);
    expect(h.kind).toBe("unknown");
  });

  it("detects rust", () => {
    expect(detectProjectEnvironment(["Cargo.toml"]).kind).toBe("rust");
  });
});
