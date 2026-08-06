import { useState } from "react";
import { profileApi, type LocalProfile } from "../../lib/api/profile";
import { ProviderSetup } from "./ProviderSetup";
import { GithubTokenField } from "../GithubTokenField";
import { Card } from "../kit";
import { OnboardingFlowWorkflows } from "./OnboardingFlowWorkflows";
import type { WorkflowType } from "../../lib/api/chat";

interface Props {
  onComplete: (profile: LocalProfile) => void;
}

export function OnboardingFlow({ onComplete }: Props) {
  const [step, setStep] = useState<"name" | "workflows" | "provider">("name");
  const [displayName, setDisplayName] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleNameSubmit = async () => {
    const name = displayName.trim();
    if (!name) { setError("Please enter a name"); return; }
    setSaving(true);
    setError("");
    try {
      await profileApi.create(name);
      await profileApi.completeOnboarding();
      setStep("workflows");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save profile");
      setSaving(false);
    }
  };

  // Workflows step done — the preference is already persisted inside the step;
  // advance to provider configuration.
  const handleWorkflowsComplete = (_preferred: WorkflowType | null) => {
    setSaving(true);
    setStep("provider");
  };

  const handleContinue = async () => {
    // FE-H1: the field is camelCase `githubToken` (matches backend GET shape).
    const token = githubToken.trim();
    if (token) {
      try { await profileApi.update({ githubToken: token }) } catch { /* non-blocking */ }
    }
    try {
      const p = await profileApi.get();
      if (p) onComplete(p);
    } catch {
      // Continue gracefully instead of dead-ending the first-run flow on a
      // profile fetch error — the profile is re-synced later.
    }
  };

  if (step === "name") {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <div className="text-4xl mb-2">⚡</div>
            <h1 className="text-2xl font-bold text-foreground">Welcome to AIC-ADE</h1>
            <p className="text-sm text-muted-foreground mt-2">AI-powered engineering platform</p>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground">What should we call you?</label>
              <input
                type="text" value={displayName}
                onChange={(e) => { setDisplayName(e.target.value); setError(""); }}
                onKeyDown={(e) => e.key === "Enter" && handleNameSubmit()}
                placeholder="Your name"
                className="mt-2 w-full rounded-lg border border-border bg-background px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500"
                autoFocus disabled={saving}
              />
              {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
            </div>
            <button onClick={handleNameSubmit} disabled={saving || !displayName.trim()}
              className="w-full rounded-lg bg-cyan-500 px-4 py-3 font-medium text-black transition hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed">
              {saving ? "Saving…" : "Continue"}
            </button>
          </div>
          <p className="text-xs text-center text-muted-foreground">Your profile is stored locally. No account needed.</p>
        </div>
      </div>
    );
  }

  // Workflows step — pick the primary way of working.
  if (step === "workflows") {
    return <OnboardingFlowWorkflows displayName={displayName} onComplete={handleWorkflowsComplete} />;
  }

  // Provider setup step
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-2xl p-8">
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-foreground">Welcome, {displayName}!</h2>
          <p className="text-sm text-muted-foreground mt-1">Configure an AI provider to get started</p>
        </div>
        <ProviderSetup mode="fre" />
        <Card className="mt-4 p-4">
          <GithubTokenField
            id="ghp-onboarding"
            value={githubToken}
            onChange={setGithubToken}
          />
        </Card>
        <div className="mt-6 text-center space-y-2">
          <button onClick={handleContinue}
            className="rounded-lg bg-cyan-500 px-6 py-3 font-medium text-black hover:bg-cyan-400">
            Continue to Dashboard →
          </button>
          <p className="text-[11px] text-muted-foreground/60">
            GitHub token is optional — you can add it later in Settings → Providers.
          </p>
        </div>
      </div>
    </div>
  );
}