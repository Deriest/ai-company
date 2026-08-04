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
}

/**
 * Error boundary — catches render errors in the wrapped subtree so a single
 * uncaught render error cannot unmount the whole React tree to a white screen.
 * The root boundary shows a full-screen fallback with a "Reload App" button;
 * per-view boundaries (compact) show a small "View failed to render" message.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, errorInfo: unknown) {
    console.error("Render error:", error, errorInfo);
  }

  // resetKey pattern: clear the error state when the view changes instead of
  // remounting the whole subtree via key={view}. A broken view still re-shows
  // its fallback on return (the render error re-fires), while healthy hidden
  // views keep their internal state across navigation.
  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const label = this.props.label ?? "Something went wrong";
      if (this.props.compact) {
        return (
          <div className="flex h-full min-h-[40vh] w-full flex-col items-center justify-center gap-3 p-6 text-center">
            <div className="text-sm font-semibold text-destructive">{label}</div>
            <button
              type="button"
              onClick={this.handleReload}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Reload App
            </button>
          </div>
        );
      }
      return (
        <div className="flex min-h-screen w-full flex-col items-center justify-center gap-4 bg-background p-6 text-center">
          <div className="text-lg font-semibold text-foreground">{label}</div>
          <div className="max-w-md text-sm text-muted-foreground">
            The app hit an unexpected error. Reload to continue.
          </div>
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Reload App
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}