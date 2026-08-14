import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Message shown in the fallback (default: "Something went wrong"). */
  label?: string;
  /** When true, render a compact in-place fallback (used per-view). */
  compact?: boolean;
  /**
   * When this value changes, the boundary clears its error state without
   * remounting the wrapped subtree. Used by the per-view boundary so hidden
   * views keep their internal state (scroll, form fields, in-flight fetches)
   * while a render error in one view doesn't leak into the next view.
   */
  resetKey?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  /** The captured error so the fallback can show *why* it failed. */
  error: Error | null;
}

const STORAGE_KEY = "aicade:lastRenderError";
const ERROR_CLIP = 4000;

/** Best-effort human-readable description of an arbitrary thrown value. */
function describeError(e: Error): Error {
  return e instanceof Error
    ? e
    : new Error(`Non-Error value thrown: ${String(e)}`);
}

/**
 * Error boundary — catches render errors in the wrapped subtree so a single
 * uncaught render error cannot unmount the whole React tree to a white screen.
 * The root boundary shows a full-screen fallback with a "Reload App" button;
 * per-view boundaries (compact) show a small "View failed to render" message.
 *
 * The caught error message + stack are shown in the fallback (and stashed in
 * localStorage) so a failure is actionable instead of a generic "Something
 * went wrong".
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    const normalized = describeError(error as Error);
    return { hasError: true, error: normalized };
  }

  componentDidCatch(error: unknown, errorInfo: unknown) {
    const normalized = describeError(error as Error);
    const stack = (normalized.stack || "")
      // Keep the banner short; the full trace is already in DevTools.
      .slice(0, ERROR_CLIP);
    console.error("[ErrorBoundary] Render error:", normalized, errorInfo);
    // Persist so the crash reason survives a "Reload App" click and can be
    // reported from the Settings/About crash diagnostics.
    try {
      const snapshot = {
        message: normalized.message || "Unknown error",
        stack,
        componentStack:
          typeof errorInfo === "object" && errorInfo && "componentStack" in errorInfo
            ? String((errorInfo as { componentStack?: unknown }).componentStack)
            : "",
        at: new Date().toISOString(),
      };
      const prev: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      const ring = Array.isArray(prev) ? prev.slice(-9) : [];
      ring.push(snapshot);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ring));
    } catch {
      // storage may be unavailable; the console.error above is the fallback
    }
  }

  // resetKey pattern: clear the error state when the view changes instead of
  // remounting the whole subtree via key={view}. A broken view still re-shows
  // its fallback on return (the render error re-fires), while healthy hidden
  // views keep their internal state across navigation.
  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
    }
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleCopy = async () => {
    const { error } = this.state;
    const text = error
      ? `${error.message}\n\n${error.stack || ""}`
      : "(no error captured)";
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // clipboard may be unavailable in some webviews — ignore
    }
  };

  render() {
    if (this.state.hasError) {
      const label = this.props.label ?? "Something went wrong";
      const { error } = this.state;
      const detail = error?.message || "Unknown error";
      const stack = error?.stack || "";
      if (this.props.compact) {
        return (
          <div className="flex h-full min-h-[40vh] w-full flex-col items-center justify-center gap-3 p-6 text-center">
            <div className="text-sm font-semibold text-destructive">{label}</div>
            <p className="break-all text-xs text-muted-foreground">{detail}</p>
            {stack ? (
              <pre className="max-h-48 max-w-full overflow-auto rounded-lg border border-border/60 bg-muted/40 p-3 text-left font-mono text-[10px] leading-relaxed text-foreground/80">
                {stack.slice(0, ERROR_CLIP)}
              </pre>
            ) : null}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={this.handleCopy}
                className="rounded-lg bg-muted px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/70"
              >
                Copy error
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Reload App
              </button>
            </div>
          </div>
        );
      }
      return (
        <div className="flex min-h-screen w-full flex-col items-center justify-center gap-4 bg-background p-6 text-center">
          <div className="text-lg font-semibold text-foreground">{label}</div>
          <div className="max-w-md text-sm text-muted-foreground">
            The app hit an unexpected error. Reload to continue.
          </div>
          <div className="w-full max-w-2xl text-left">
            <p className="break-all text-sm font-medium text-destructive">{detail}</p>
            {stack ? (
              <pre className="mt-2 max-h-[40vh] overflow-auto rounded-lg border border-border/60 bg-muted/40 p-3 font-mono text-[11px] leading-relaxed text-foreground/80">
                {stack.slice(0, ERROR_CLIP)}
              </pre>
            ) : null}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={this.handleCopy}
              className="rounded-lg bg-muted px-5 py-2 text-sm font-medium text-foreground hover:bg-muted/70"
            >
              Copy error
            </button>
            <button
              type="button"
              onClick={this.handleReload}
              className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Reload App
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export { STORAGE_KEY };