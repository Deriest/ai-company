/** Provider / model display helpers — PROVIDER ≠ MODEL. */

export type ProviderLike = {
  id?: string;
  name?: string;
  base_url?: string;
  model?: string;
  models?: Record<string, string> | null;
  is_active?: boolean;
};

export function resolveDefaultModelId(p?: ProviderLike | null): string {
  if (!p) return "";
  if (typeof p.model === "string" && p.model.trim()) return p.model.trim();
  const models = p.models;
  if (!models || typeof models !== "object") return "";
  for (const key of ["default", "sprinter", "crafter", "thinker"] as const) {
    const v = models[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  for (const v of Object.values(models)) {
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

/** e.g. "gpt-4o-mini · OpenAI" */
export function formatModelLabel(p?: ProviderLike | null): string {
  if (!p) return "Configure Provider";
  const model = resolveDefaultModelId(p);
  const name = (p.name || "Provider").trim() || "Provider";
  if (model) return `${model} · ${name}`;
  return `Select model · ${name}`;
}

export function activeProvider(list: ProviderLike[] | null | undefined): ProviderLike | null {
  if (!Array.isArray(list) || list.length === 0) return null;
  return list.find((p) => p.is_active) || list[0] || null;
}
