import { describe, expect, it } from "vitest";

/** Pure helpers mirroring main-process path policy for unit proof. */
function resolveSafe(target: string, roots: string[]): string {
  const path = require("node:path") as typeof import("node:path");
  const resolved = path.resolve(target);
  const ok = roots
    .map((r) => path.resolve(r))
    .some((root) => resolved === root || resolved.startsWith(root + path.sep));
  if (!ok) throw new Error(`path not allowed: ${resolved}`);
  return resolved;
}

describe("path allowlist policy", () => {
  it("allows under project root", () => {
    const root = "/home/tvd/projects/demo";
    expect(resolveSafe("/home/tvd/projects/demo/src/a.ts", [root])).toContain("demo");
  });

  it("blocks outside roots", () => {
    expect(() => resolveSafe("/etc/passwd", ["/home/tvd/projects/demo"])).toThrow(/not allowed/);
  });
});
