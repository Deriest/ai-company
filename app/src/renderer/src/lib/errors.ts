/** Map technical failures to product-facing errors. */

export type FriendlyError = {
  title: string;
  message: string;
  action?: string;
  retryable: boolean;
  technical?: string;
  /** If true, this error should be silently ignored (not shown to user). */
  silent?: boolean;
};

export function friendlyError(err: unknown): FriendlyError {
  const raw = err instanceof Error ? err.message : String(err || "Unknown error");
  const lower = raw.toLowerCase();

  // Auth errors — the runtimeClient auto-recovers 401/403 via refreshToken(),
  // so if this error still reaches us, recovery already failed. Show a helpful
  // message instead of silently swallowing (the user needs to know why data
  // isn't loading).
  if (
    lower.includes("401") ||
    lower.includes("unauthorized") ||
    lower.includes("not authenticated") ||
    lower.includes("could not validate credentials")
  ) {
    return {
      title: "Session expired",
      message: "Your session could not be restored. The local engine may still be starting.",
      action: "Wait a moment — AIC will retry automatically. If this persists, restart the app.",
      retryable: true,
      technical: raw,
    };
  }

  // Provider model discovery failures (must precede generic "failed to fetch")
  if (
    lower.includes("failed to fetch models") ||
    (lower.includes("/models") && (lower.includes("502") || lower.includes("timeout")))
  ) {
    return {
      title: "Provider unreachable",
      message: "AIC could not list models from this provider endpoint.",
      action: "Verify the API endpoint, API key, and network access — then Test Connection again.",
      retryable: true,
      technical: raw,
    };
  }

  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("load failed") ||
    lower.includes("network request failed")
  ) {
    return {
      title: "Cannot reach local engine",
      message:
        "AIC ADE could not connect to its built-in engineering engine. It may still be starting, or it crashed.",
      action: "Wait a moment and retry. If this persists, restart AIC ADE.",
      retryable: true,
      technical: raw,
    };
  }

  if (lower.includes("econnrefused") || lower.includes("connection refused")) {
    return {
      title: "Engine not listening",
      message: "The local engine is not accepting connections yet.",
      action: "Retry in a few seconds. The engine starts automatically with the app.",
      retryable: true,
      technical: raw,
    };
  }

  if (lower.includes("403") || lower.includes("forbidden")) {
    return {
      title: "Permission denied",
      message: "You don't have permission for this action, or your session is invalid.",
      action: "Wait a moment and retry. If this persists, restart the app.",
      retryable: true,
      technical: raw,
    };
  }

  // LLM pipeline errors (502/503 from conversations API)
  if (lower.includes("503") || lower.includes("no ai provider") || lower.includes("no llm provider")) {
    return {
      title: "No AI provider",
      message: "Hermes needs an AI provider to respond. Add one in Settings → AI Providers.",
      action: "Open Settings and connect a provider.",
      retryable: false,
      technical: raw,
    };
  }
  if (lower.includes("502") || lower.includes("llm request failed") || lower.includes("llm inference")) {
    return {
      title: "AI request failed",
      message: "The LLM provider returned an error. Check your API key and provider status.",
      action: "Verify your provider settings and try again.",
      retryable: true,
      technical: raw,
    };
  }

  if (lower.includes("404")) {
    return {
      title: "Not found",
      message: "The requested resource is missing or was removed.",
      action: "Refresh the view or open a different item.",
      retryable: true,
      technical: raw,
    };
  }

  if (lower.includes("timeout") || lower.includes("timed out") || lower.includes("deadline")) {
    return {
      title: "Request timed out",
      message: "The engine took too long to respond.",
      action: "Retry. Large model discovery can take longer than usual.",
      retryable: true,
      technical: raw,
    };
  }

  if (lower.includes("502") || lower.includes("failed to fetch models")) {
    return {
      title: "Provider unreachable",
      message: "AIC could not list models from this provider endpoint.",
      action: "Verify the API endpoint, API key, and network access — then Test Connection again.",
      retryable: true,
      technical: raw,
    };
  }

  // Generic API shape: METHOD path → status: detail
  const m = /→\s*(\d{3}):\s*(.*)$/.exec(raw);
  if (m) {
    return {
      title: `Request failed (${m[1]})`,
      message: m[2] || "The engine returned an error.",
      action: "Review the details and retry.",
      retryable: Number(m[1]) >= 500 || m[1] === "429",
      technical: raw,
    };
  }

  return {
    title: "Something went wrong",
    message: raw.slice(0, 220),
    action: "Retry the action. If it keeps failing, check Diagnostics in Settings.",
    retryable: true,
    technical: raw,
  };
}

export function formatFriendlyError(err: unknown): string {
  const f = friendlyError(err);
  if (f.silent) return ""; // Reserved for truly ignorable errors
  return [f.title, f.message, f.action].filter(Boolean).join(" — ");
}
