/** Detect project runtime from common manifest files (project env ≠ app engine). */

export type ProjectKind =
  | "node"
  | "python"
  | "rust"
  | "go"
  | "java"
  | "dotnet"
  | "ruby"
  | "php"
  | "mixed"
  | "unknown";

export type ProjectEnvironmentHint = {
  kind: ProjectKind;
  label: string;
  manifests: string[];
  suggestedActions: string[];
};

const RULES: Array<{
  kind: ProjectKind;
  files: string[];
  label: string;
  actions: string[];
}> = [
  {
    kind: "node",
    files: ["package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"],
    label: "Node.js / JavaScript",
    actions: ["Install dependencies (npm/pnpm/yarn)", "Run scripts from package.json"],
  },
  {
    kind: "python",
    files: ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "poetry.lock"],
    label: "Python",
    actions: ["Create .venv", "Install requirements", "Run pytest / uvicorn"],
  },
  {
    kind: "rust",
    files: ["Cargo.toml"],
    label: "Rust",
    actions: ["cargo build", "cargo test"],
  },
  {
    kind: "go",
    files: ["go.mod"],
    label: "Go",
    actions: ["go mod download", "go test ./..."],
  },
  {
    kind: "java",
    files: ["pom.xml", "build.gradle", "build.gradle.kts"],
    label: "Java / JVM",
    actions: ["Restore Gradle/Maven deps", "Run tests"],
  },
  {
    kind: "dotnet",
    files: [".csproj", ".sln", "global.json"],
    label: ".NET",
    actions: ["dotnet restore", "dotnet build"],
  },
  {
    kind: "ruby",
    files: ["Gemfile"],
    label: "Ruby",
    actions: ["bundle install"],
  },
  {
    kind: "php",
    files: ["composer.json"],
    label: "PHP",
    actions: ["composer install"],
  },
];

/** fileNames: basenames found at project root (and shallow children if provided). */
export function detectProjectEnvironment(fileNames: string[]): ProjectEnvironmentHint {
  const lower = new Set(fileNames.map((f) => f.toLowerCase().split(/[/\\]/).pop() || f.toLowerCase()));
  const hits: ProjectEnvironmentHint[] = [];

  for (const rule of RULES) {
    const matched = rule.files.filter((f) => {
      const base = f.toLowerCase();
      if (base.startsWith(".")) {
        // extension style e.g. .csproj — match suffix
        return [...lower].some((n) => n.endsWith(base));
      }
      return lower.has(base);
    });
    if (matched.length) {
      hits.push({
        kind: rule.kind,
        label: rule.label,
        manifests: matched,
        suggestedActions: rule.actions,
      });
    }
  }

  if (hits.length === 0) {
    return {
      kind: "unknown",
      label: "Unknown project type",
      manifests: [],
      suggestedActions: ["Open folder and explore files", "Ask Hermes to inspect the repo"],
    };
  }
  if (hits.length === 1) return hits[0];
  return {
    kind: "mixed",
    label: hits.map((h) => h.label).join(" + "),
    manifests: hits.flatMap((h) => h.manifests),
    suggestedActions: hits.flatMap((h) => h.suggestedActions).slice(0, 6),
  };
}
