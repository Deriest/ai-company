/** AIC FSM phases — mirrors backend workflow/fsm.py (display only). */

export const PHASE_ORDER = [
  "created",
  "discovery",
  "investigate",
  "planning",
  "implementation",
  "verification",
  "closeout",
  "completed",
] as const;

export type Phase = (typeof PHASE_ORDER)[number] | string;

export function normalizePhase(phase: string | null | undefined): string {
  return String(phase || "").toLowerCase().trim();
}

export function phaseIndex(phase: string | null | undefined): number {
  const p = normalizePhase(phase);
  const i = PHASE_ORDER.indexOf(p as (typeof PHASE_ORDER)[number]);
  return i;
}

export function isTerminal(phase: string | null | undefined): boolean {
  const p = normalizePhase(phase);
  return p === "completed" || p === "cancelled" || p === "blocked" || p === "failed";
}

export function groupTasksByPhase(tasks: Array<Record<string, unknown>>): Record<string, Array<Record<string, unknown>>> {
  const buckets: Record<string, Array<Record<string, unknown>>> = {};
  for (const ph of PHASE_ORDER) buckets[ph] = [];
  buckets.other = [];
  for (const t of tasks) {
    const p = normalizePhase(String(t.status || ""));
    if (p in buckets && p !== "other") buckets[p].push(t);
    else if (isTerminal(p) && p !== "completed") {
      if (!buckets[p]) buckets[p] = [];
      buckets[p].push(t);
    } else if (p === "completed") buckets.completed.push(t);
    else buckets.other.push(t);
  }
  return buckets;
}
