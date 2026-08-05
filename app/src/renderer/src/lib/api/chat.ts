import { apiClient } from "./client";
import { MessageRecord } from "./conversations";

// PERF-FIX: cache the backend port after the first IPC round-trip so every
// stream call doesn't pay a getBackendStatus IPC hop. The cache is bounded
// by a TTL so a backend restart onto a different port (8000-8099) is picked
// up within a minute instead of being cached forever.
const PORT_CACHE_TTL_MS = 60_000;
let cachedBackendPort: number | null = null;
let cachedBackendPortAt = 0;

async function getBackendPort(): Promise<number> {
  if (cachedBackendPort !== null && Date.now() - cachedBackendPortAt < PORT_CACHE_TTL_MS) {
    return cachedBackendPort;
  }
  const port = await (window as any).aic?.getBackendStatus()?.then((s: any) => s.port).catch(() => 8000) || 8000;
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

/** Clarify question from the backend when a task lacks project/workspace details. */
export interface ClarifyQuestion {
  id: string;
  question: string;
  options?: string[];
}

export interface ClarifyPayload {
  reason?: string;
  questions: ClarifyQuestion[];
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

/** All event types from the backend SSE stream */
export type StreamEvent =
  | { type: "chunk"; content: string }
  | { type: "rewrite"; content: string }
  | { type: "tool_start"; tool: string; args: Record<string, any> }
  | { type: "tool_result"; tool_call: ToolCallData }
  | { type: "file_diff"; path: string; before: string; after: string; action: string }
  | { type: "shell_output"; command: string; chunk: string; exit_code: number | null; status: string }
  | { type: "todo_update"; items: TodoItemData[] }
  | { type: "files_modified"; paths: string[] }
  | { type: "deliverables"; deliverables: DeliverableSummary }
  | { type: "done"; intent?: string; metadata?: Record<string, any> }
  | { type: "error"; error: string }
  | { type: "cancelled"; reason?: string }
  | { type: "overflow_warning"; summary?: string };

/** Callback interface for stream events */
export interface StreamCallbacks {
  onChunk: (content: string) => void;
  onRewrite?: (content: string) => void;
  onToolStart: (tool: string, args: Record<string, any>) => void;
  onToolResult: (toolCall: ToolCallData) => void;
  onFileDiff: (diff: FileDiffData) => void;
  onShellOutput: (output: ShellOutputData) => void;
  onTodoUpdate: (items: TodoItemData[]) => void;
  onFilesModified: (paths: string[]) => void;
  onDone: (metadata?: Record<string, any>) => void;
  onError: (error: string) => void;
}

export const chatApi = {
  async complete(payload: {
    conversation_id: string;
    messages: { role: string; content: string }[];
    provider_id?: string;
    model_id?: string;
    worker_role?: string;
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  }): Promise<MessageRecord> {
    return apiClient.post<MessageRecord>("/chat", payload);
  },

  /**
   * Stream with full tool event support.
   * Parses all SSE event types and dispatches to callbacks.
   */
  async streamWithTools(
    payload: {
      conversation_id: string;
      messages: { role: string; content: string }[];
      provider_id?: string;
      model_id?: string;
      worker_role?: string;
      temperature?: number;
      top_p?: number;
      max_tokens?: number;
    },
    callbacks: StreamCallbacks,
  ): Promise<() => void> {
    const port = await getBackendPort();
    const url = `http://127.0.0.1:${port}/chat/stream`;
    const ac = new AbortController();

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, stream: true }),
      signal: ac.signal,
    }).then(async (res) => {
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
          const dataStr = line.substring(6);
          if (dataStr === "[DONE]") { callbacks.onDone(); return; }

          try {
            const evt: StreamEvent = JSON.parse(dataStr);
            switch (evt.type) {
              case "chunk":
                callbacks.onChunk(evt.content);
                break;
              case "rewrite":
                callbacks.onRewrite?.(evt.content);
                break;
              case "tool_start":
                callbacks.onToolStart(evt.tool, evt.args);
                break;
              case "tool_result":
                callbacks.onToolResult(evt.tool_call);
                break;
              case "file_diff":
                callbacks.onFileDiff({ path: evt.path, before: evt.before, after: evt.after, action: evt.action });
                break;
              case "shell_output":
                callbacks.onShellOutput({ command: evt.command, chunk: evt.chunk, exit_code: evt.exit_code ?? null, status: evt.status });
                break;
              case "todo_update":
                callbacks.onTodoUpdate(evt.items);
                break;
              case "files_modified":
                callbacks.onFilesModified(evt.paths);
                break;
              case "done":
                callbacks.onDone(evt.metadata);
                return;
              case "error":
                callbacks.onError(evt.error);
                return;
            }
          } catch { /* ignore parse errors for partial chunks */ }
        }
      }
      callbacks.onDone();
    }).catch((e) => {
      if (e.name !== "AbortError") callbacks.onError(String(e));
    });

    return () => ac.abort();
  },

  /** Legacy stream (no tools) — backward compat */
  async stream(payload: {
    conversation_id: string;
    messages: { role: string; content: string }[];
    provider_id?: string;
    model_id?: string;
    worker_role?: string;
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  }, onChunk: (chunk: string) => void, onDone: () => void, onError: (err: any) => void): Promise<() => void> {
    return chatApi.streamWithTools(payload, {
      onChunk,
      onRewrite: () => {},
      onToolStart: () => {},
      onToolResult: () => {},
      onFileDiff: () => {},
      onShellOutput: () => {},
      onTodoUpdate: () => {},
      onFilesModified: () => {},
      onDone,
      onError: (err) => onError(new Error(err)),
    });
  },

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
    const port = await getBackendPort();
    const url = `http://127.0.0.1:${port}/chat/execute`;
    const ac = new AbortController();

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ac.signal,
    }).then(async (res) => {
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
