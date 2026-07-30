/** Canonical 15 — source of truth for Live Company (not web UI copy). */
export type WorkerTier = "system" | "thinker" | "crafter" | "sprinter";
export type Department = "Leadership" | "Product" | "Engineering" | "Platform";

export type CanonicalWorker = {
  id: string;
  name: string;
  role: string;
  tier: WorkerTier;
  department: Department;
};

export const CANONICAL_WORKFORCE: CanonicalWorker[] = [
  { id: "hermes", name: "Hermes", role: "Dispatcher", tier: "system", department: "Leadership" },
  { id: "rex", name: "Rex", role: "Governor", tier: "sprinter", department: "Leadership" },
  { id: "pm", name: "Aria", role: "Product Manager", tier: "thinker", department: "Product" },
  { id: "research", name: "Sage", role: "Researcher", tier: "thinker", department: "Product" },
  { id: "designer", name: "Luna", role: "Designer", tier: "crafter", department: "Product" },
  { id: "documentation", name: "Echo", role: "Documentation Engineer", tier: "sprinter", department: "Product" },
  { id: "architect", name: "Atlas", role: "Architect", tier: "thinker", department: "Engineering" },
  { id: "backend", name: "Hugo", role: "Backend Engineer", tier: "crafter", department: "Engineering" },
  { id: "frontend", name: "Leo", role: "Frontend Engineer", tier: "crafter", department: "Engineering" },
  { id: "qa", name: "Eve", role: "QA Engineer", tier: "sprinter", department: "Engineering" },
  { id: "performance", name: "Pulse", role: "Performance Engineer", tier: "sprinter", department: "Engineering" },
  { id: "database", name: "Nova", role: "Data Engineer", tier: "crafter", department: "Platform" },
  { id: "nexus", name: "Nexus", role: "Integration Engineer", tier: "crafter", department: "Platform" },
  { id: "flint", name: "Flint", role: "Infrastructure Engineer", tier: "crafter", department: "Platform" },
  { id: "security", name: "Sentinel", role: "Security Engineer", tier: "crafter", department: "Platform" },
];

export function getWorker(id: string): CanonicalWorker | undefined {
  return CANONICAL_WORKFORCE.find((w) => w.id === id);
}
