import { describe, expect, it } from "vitest";
import { CANONICAL_WORKFORCE } from "./workforce";

describe("fileTree filter logic", () => {
  it("filters tree nodes by name match", () => {
    type Node = { name: string; path: string; isDirectory: boolean; children?: Node[] };
    const tree: Node[] = [
      { name: "src", path: "/src", isDirectory: true, children: [
        { name: "app.tsx", path: "/src/app.tsx", isDirectory: false },
        { name: "index.ts", path: "/src/index.ts", isDirectory: false },
      ]},
      { name: "README.md", path: "/README.md", isDirectory: false },
    ];

    function filter(n: Node): boolean {
      const q = "app";
      if (n.name.toLowerCase().includes(q)) return true;
      if (n.children) return n.children.some(filter);
      return false;
    }

    const result = tree.filter(filter);
    // "src" matches because its child "app.tsx" contains "app"
    // "README.md" does not match "app"
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("src");
  });

  it("filters correctly for exact match", () => {
    type Node = { name: string; path: string; isDirectory: boolean; children?: Node[] };
    const tree: Node[] = [
      { name: "src", path: "/src", isDirectory: true, children: [
        { name: "app.tsx", path: "/src/app.tsx", isDirectory: false },
      ]},
      { name: "README.md", path: "/README.md", isDirectory: false },
    ];

    function filter(n: Node): boolean {
      const q = "readme";
      if (n.name.toLowerCase().includes(q)) return true;
      if (n.children) return n.children.some(filter);
      return false;
    }

    const result = tree.filter(filter);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("README.md");
  });
});

describe("conversation switch", () => {
  it("maps API message objects to Msg type", () => {
    const apiMsgs = [
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
      { sender: "user", text: "via sender field" },
    ];

    const loaded = (apiMsgs as Array<Record<string, unknown>>).map((o) => ({
      role: (String(o.role || o.sender || "") === "user" ? "user" : "assistant") as "user" | "assistant",
      content: String(o.content || o.text || ""),
    })).filter((m) => m.content);

    expect(loaded).toHaveLength(3);
    expect(loaded[0].role).toBe("user");
    expect(loaded[0].content).toBe("hello");
    expect(loaded[1].role).toBe("assistant");
    expect(loaded[2].role).toBe("user");
    expect(loaded[2].content).toBe("via sender field");
  });
});

describe("canonical workforce (regression)", () => {
  it("still has 15 workers including Hermes", () => {
    expect(CANONICAL_WORKFORCE).toHaveLength(15);
    expect(CANONICAL_WORKFORCE.some((w) => w.id === "hermes")).toBe(true);
  });
});
