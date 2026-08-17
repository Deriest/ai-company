import { getApiToken } from "./client";

// PERF-FIX: cache the backend port after the first IPC round-trip so every
// stream call doesn't pay a getBackendStatus IPC hop. The cache is bounded
// by a TTL so a backend restart onto a different port (8000-8099) is picked
// up within a minute instead of being cached forever.
// Reduced TTL for faster invalidation when backend restarts with new port
// 10 seconds is reasonable: allows brief network glitches while catching restarts quickly
const PORT_CACHE_TTL_MS = 10_000;
let cachedBackendPort: number | null = null;
let cachedBackendPortAt = 0;

/** M5: drop the cached port so the next getBackendPort() re-resolves via IPC. */
function invalidatePortCache(): void {
  cachedBackendPort = null;
  cachedBackendPortAt = 0;
}

async function getBackendPort(): Promise<number> {
  if (cachedBackendPort !== null && Date.now() - cachedBackendPortAt < PORT_CACHE_TTL_MS) {
    return cachedBackendPort;
  }
  let port = 8000;
  if (typeof window !== "undefined" && window.aic?.getBackendStatus) {
    port = await window.aic.getBackendStatus().then((s) => s.port).catch(() => 8000) || 8000;
  }
  cachedBackendPort = port;
  cachedBackendPortAt = Date.now();
  return port;
}

/** Structured tool call from backend SSE events */
export interface ToolCallData {
  id: string;
  type: string;         // read_file, write_file, shell, explore, search
  label: string;
  status: string;       // pending, running, completed, error
  args: Record<string, any>;
  result: Record<string, any>;
  output: string;
  duration_ms: number;
  timestamp: string;
  error: string | null;
}

/** File diff from backend SSE events */
export interface FileDiffData {
  path: string;
  before: string;
  after: string;
  action: string; // created, modified, deleted
}

/** Shell output chunk from backend SSE events */
export interface ShellOutputData {
  command: string;
  chunk: string;
  exit_code: number | null;
  status: string; // running, completed, error
}

/** Todo item from backend SSE events */
export interface TodoItemData {
  id: string;
  content: string;
  status: string;  // pending, in_progress, completed, cancelled
  priority: string; // high, medium, low
}

/** Deliverable summary from backend */
export interface DeliverableFile {
  path: string;
  action: string;
  size: number;
  preview: string;
}

export interface DeliverableSummary {
  files: DeliverableFile[];
  files_created: string[];
  files_modified: string[];
  tests: {
    passed: number;
    failed: number;
    output: string;
  };
  shell_commands: string[];
  errors: { tool: string; error: string }[];
}

/** Clarify question from the backend when a task lacks project/workspace details. */
/** Workflow/task types mirroring the backend's WORKFLOW_PLANS enum. */
export type WorkflowType =
  | "build"
  | "feature"
  | "bugfix"
  | "refactor"
  | "bughunt"
  | "test"
  | "docs"
  | "infra"
  | "research";

/** Level of execution depth for a workflow. Mirrors backend ExecutionLevel QUICK/STANDARD/EXTENDED/FULL. */
export type WorkflowLevel = "quick" | "standard" | "extended" | "full";

/** Tag attached to messages indicating which workflow type/level to run. */
export interface WorkflowTag {
  workflow: WorkflowType;
  level?: WorkflowLevel;
}

export interface ClarifyQuestion {
  id: string;
  question: string;
  options?: string[];
}

export interface ClarifyPayload {
  reason?: string;
  questions: ClarifyQuestion[];
}

export const chatApi = {
  async executeAgent(payload: {
    conversation_id: string;
    messages: { role: string; content: string }[];
    worker_role?: string;
    model_tier?: string;
    attachments?: { name: string; mime_type: string; data_url: string }[];
    /** Active project root — tells the dispatcher where to create project folders. */
    workspace?: string;
    /** Active project record id — conversations/agents run scoped to this project. */
    project_id?: string;
    /** Workflow tags — which task-type pipeline (bugfix/build/etc) to run. */
    tags?: WorkflowTag[];
  }, callbacks: {
    onChunk: (content: string) => void;
    onToolStart: (tool: string, args: Record<string, any>, callId: string) => void;
    onToolResult: (toolCall: ToolCallData) => void;
    onStatus: (status: string, data: any) => void;
    onDeliverables: (deliverables: DeliverableSummary) => void;
    onDone: (intent: string) => void;
    onError: (error: string) => void;
    /** Backend asks for missing details (project/workspace) — render, don't auto-spawn. */
    onClarify?: (payload: ClarifyPayload) => void;
  }): Promise<() => void> {
    const ac = new AbortController();

    // M5: open the stream, retrying ONCE with a freshly resolved port on
    // connection failure (non-2xx or network error) — a backend crash-restart
    // can land on a new port (8000-8099), leaving the cached port stale.
    const openStream = async (): Promise<Response> => {
      const open = async () =>
        fetch(`http://127.0.0.1:${await getBackendPort()}/chat/execute`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(getApiToken() ? { Authorization: `Bearer ${getApiToken()}` } : {}),
          },
          body: JSON.stringify(payload),
          signal: ac.signal,
        });
      try {
        const res = await open();
        if (res.ok) return res;
        invalidatePortCache();
        return await open();
      } catch (e) {
        if ((e as Error)?.name === "AbortError") throw e;
        invalidatePortCache();
        return await open();
      }
    };

    openStream().then(async (res) => {
      // QA-HARDENING: surface non-2xx responses (e.g. 413 body too large)
      // via onError instead of silently parsing the JSON error body as SSE
      // and firing an empty onDone.
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const body = await res.json();
          if (body?.detail) detail = String(body.detail);
        } catch { /* non-JSON error body */ }
        callbacks.onError(detail);
        return;
      }
      if (!res.body) throw new Error("No body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Cap the SSE buffer so a misbehaving stream can never grow unbounded.
        // Keep only the tail after the last complete event boundary.
        if (buffer.length > 1_000_000) {
          const lastBreak = buffer.lastIndexOf('\n\n');
          buffer = lastBreak >= 0 ? buffer.slice(lastBreak + 2) : '';
        }

        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.substring(6));
            switch (evt.type) {
              case "intent":
                callbacks.onStatus("intent", evt);
                break;
              case "status":
                callbacks.onStatus(evt.status, evt);
                break;
              case "chunk":
                callbacks.onChunk(evt.content || "");
                break;
              case "tool_start":
                callbacks.onToolStart(evt.tool, evt.args || {}, evt.call_id || "");
                break;
              case "tool_result":
                callbacks.onToolResult(evt.tool_call || evt);
                break;
              case "deliverables":
                callbacks.onDeliverables(evt.deliverables);
                break;
              case "clarify":
                // Backend needs more detail (missing project/workspace). Forward
                // the payload so the UI can render the questions; the stream
                // continues and includes a later "done" event.
                callbacks.onClarify?.(evt.data);
                break;
              case "done":
                callbacks.onDone(evt.intent || "");
                return;
              case "error":
                callbacks.onError(evt.error || "Unknown error");
                return;
              case "cancelled":
                // Cooperative cancel (Stop): forward as a status so the UI can
                // keep its *[stopped]* marker instead of the stream closing
                // cleanly and firing onDone("") with partial content.
                callbacks.onStatus("cancelled", evt);
                return;
              case "overflow_warning":
                callbacks.onStatus("overflow_warning", evt);
                break;
            }
          } catch { /* ignore parse errors */ }
        }
      }
      callbacks.onDone("");
    }).catch((e) => {
      if (e.name !== "AbortError") callbacks.onError(String(e));
    });

    return () => ac.abort();
  },
};
