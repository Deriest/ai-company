/** Project environment bootstrap suggestions — app runtime ≠ project runtime. */

export type BootstrapStep = {
  id: string;
  title: string;
  command: string;
  optional?: boolean;
};

export function bootstrapStepsForKind(kind: string): BootstrapStep[] {
  switch (kind) {
    case "node":
      return [
        { id: "install", title: "Install dependencies", command: "npm install" },
        { id: "test", title: "Run tests", command: "npm test", optional: true },
      ];
    case "python":
      return [
        { id: "venv", title: "Create virtualenv", command: "python3 -m venv .venv" },
        {
          id: "install",
          title: "Install requirements",
          command: ".venv/bin/pip install -r requirements.txt || .venv/bin/pip install -e .",
        },
        { id: "test", title: "Run pytest", command: ".venv/bin/pytest -q", optional: true },
      ];
    case "rust":
      return [
        { id: "build", title: "Build", command: "cargo build" },
        { id: "test", title: "Test", command: "cargo test", optional: true },
      ];
    case "go":
      return [
        { id: "mod", title: "Download modules", command: "go mod download" },
        { id: "test", title: "Test", command: "go test ./...", optional: true },
      ];
    default:
      return [];
  }
}
