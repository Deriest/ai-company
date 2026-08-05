import { AlertTriangle, FileText, RefreshCw, Zap } from "lucide-react";
import type { BootPhase } from "../types";
import type { BackendStatusInfo } from "../hooks/useBoot";
import { cn } from "../lib/utils";

const STEPS: Array<{ key: BootPhase; label: string }> = [
  { key: "launching", label: "Engine" },
  { key: "restoring_session", label: "Session" },
  { key: "loading_workspace", label: "Workspace" },
  { key: "loading_skills", label: "Skills" },
];

const PHASE_FALLBACK: Record<string, string> = {
  launching: "Launching local engineering engine…",
  restoring_session: "Restoring projects, tabs, and conversations…",
  loading_workspace: "Loading workspace…",
  loading_skills: "Preparing skills and workforce…",
  ready: "Ready",
};

function AmbientBackdrop() {
  return (
    <>
      {/* Vignette + faint grid to match the app's #05060A aesthetic */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,oklch(0.15_0.015_250)_100%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
        }}
      />
      <div className="pointer-events-none absolute -top-48 left-1/2 h-96 w-[46rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-24 h-80 w-96 rounded-full bg-info/10 blur-[130px]" />
    </>
  );
}

function LogoMark() {
  return (
    <div className="relative">
      <div className="absolute inset-0 rounded-2xl bg-primary/40 blur-2xl" />
      <div className="relative grid size-16 place-items-center rounded-2xl border border-primary/40 bg-gradient-to-br from-primary/20 via-primary/5 to-transparent">
        <Zap className="size-8 text-primary" fill="currentColor" />
      </div>
    </div>
  );
}

function PhaseStepper({ phase }: { phase: BootPhase }) {
  const currentIndex = STEPS.findIndex((s) => s.key === phase);
  const isError = phase === "error";
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const done = !isError && (currentIndex === -1 || i < currentIndex);
        const active = !isError && i === currentIndex;
        const reached = done || active;
        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5">
              <span
                className={cn(
                  "grid size-2.5 rounded-full transition-colors",
                  done && "bg-primary",
                  active && "bg-primary animate-pulse",
                  !reached && "bg-muted",
                )}
              />
              <span className={cn(
                "text-[9px] uppercase tracking-wider",
                active ? "text-foreground/80" : done ? "text-muted-foreground/70" : "text-muted-foreground/30",
              )}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <span className={cn(
                "mx-2 mb-5 h-px w-8",
                done ? "bg-primary/50" : "bg-muted",
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function BootSplash({ phase, detail, backendStatus, onRetry }: {
  phase: BootPhase;
  detail: string;
  backendStatus?: BackendStatusInfo | null;
  onRetry?: () => void;
}) {
  const isError = phase === "error" || backendStatus?.status === "error";
  const message = detail || PHASE_FALLBACK[phase] || "Starting…";

  if (isError) {
    const errorMsg = backendStatus?.error || detail || "The local engine failed to start.";
    const logFile = backendStatus?.logFile;
    return (
      <div className="relative flex h-screen items-center justify-center overflow-hidden bg-background">
        <AmbientBackdrop />
        <div className="relative w-full max-w-md px-6">
          <div className="ade-fade-up flex flex-col items-center text-center">
            <div className="grid size-14 place-items-center rounded-2xl border border-destructive/30 bg-destructive/10">
              <AlertTriangle className="size-7 text-destructive" />
            </div>
            <h1 className="mt-5 text-lg font-semibold tracking-tight">Engine failed to start</h1>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{errorMsg}</p>

            {logFile && (
              <button
                type="button"
                onClick={() => window.aic?.openPath?.(logFile)}
                className="mt-4 inline-flex max-w-full items-center gap-1.5 rounded-lg border border-border bg-card/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                title="Open backend startup log"
              >
                <FileText className="size-3.5 shrink-0" />
                <span className="truncate font-mono">{logFile}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onRetry}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <RefreshCw className="size-4" /> Retry
            </button>
            <p className="mt-4 text-[11px] text-muted-foreground/60">
              The local engine retries in the background — you can also retry manually.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex h-screen items-center justify-center overflow-hidden bg-background">
      <AmbientBackdrop />
      <div className="relative flex flex-col items-center">
        <div className="ade-fade-up">
          <LogoMark />
        </div>
        <h1 className="ade-fade-up ade-delay-1 mt-6 text-xl font-semibold tracking-tight">AIC-ADE</h1>
        <p className="ade-fade-up ade-delay-1 mt-1 text-xs text-muted-foreground">
          AI software engineering, running locally
        </p>

        <div className="ade-fade-up ade-delay-2 mt-9 flex items-center gap-3">
          <span className="relative flex size-4">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
            <span className="relative inline-flex size-4 rounded-full border-2 border-primary/40 border-t-primary ade-orbit" />
          </span>
          <span className="text-sm text-muted-foreground">{message}</span>
        </div>

        <div className="ade-fade-up ade-delay-3 mt-7">
          <PhaseStepper phase={phase} />
        </div>
      </div>
    </div>
  );
}