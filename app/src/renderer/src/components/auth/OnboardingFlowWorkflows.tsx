/**
 * OnboardingFlowWorkflows — "How do you want to work?" first-run step.
 *
 * Shown after the name step during onboarding. Renders the same workflow cards
 * as the Command Center (detailed mode) so a new user picks their primary use
 * case. The choice is persisted to localStorage AND the profile
 * (`preferred_workflow`) so ChatView can pre-select it next launch — the user
 * can always override per-message via the workflow selector.
 */
import { useState } from "react";
import { WorkflowSelector } from "../WorkflowSelector";
import { writePreferredWorkflow, type WorkflowDef } from "../../lib/workflows";
import { profileApi } from "../../lib/api/profile";
import type { WorkflowType } from "../../lib/api/chat";

interface Props {
  displayName: string;
  onComplete: (preferred: WorkflowType | null) => void;
}

export function OnboardingFlowWorkflows({ displayName, onComplete }: Props) {
  const [selected, setSelected] = useState<WorkflowType | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSelect = (wf: WorkflowDef) => {
    // Toggle: clicking the already-selected card deselects (back to auto).
    setSelected(prev => (prev === wf.type ? null : wf.type));
  };

  const handleContinue = async () => {
    setSaving(true);
    // Persist to localStorage (authoritative for the renderer) and best-effort
    // to the profile so it syncs once the backend stores preferred_workflow.
    if (selected) {
      writePreferredWorkflow(selected);
      try {
        await profileApi.update({ preferredWorkflow: selected });
      } catch {
        /* non-blocking — localStorage already has the preference */
      }
    }
    setSaving(false);
    onComplete(selected);
  };

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-2xl p-8">
        <div className="mb-6 text-center">
          <h2 className="text-xl font-bold text-foreground">How do you want to work, {displayName}?</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Pick your primary use case — we&apos;ll tailor the pipeline. You can change this per task anytime.
          </p>
        </div>

        <WorkflowSelector selected={selected} onSelect={handleSelect} detailed />

        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => onComplete(null)}
            disabled={saving}
            className="rounded-lg px-4 py-2 text-sm text-muted-foreground transition hover:text-foreground disabled:opacity-50"
          >
            Skip — decide later
          </button>
          <button
            onClick={handleContinue}
            disabled={saving}
            className="rounded-lg bg-cyan-500 px-6 py-3 font-medium text-black transition hover:bg-cyan-400 disabled:opacity-50"
          >
            {saving ? "Saving…" : selected ? "Continue →" : "Continue with auto-detect →"}
          </button>
        </div>
      </div>
    </div>
  );
}
