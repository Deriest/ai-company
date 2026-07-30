import { apiClient } from "./client";
import { MessageRecord } from "./conversations";

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

/** All event types from the backend SSE stream */
export type StreamEvent =
  | { type: "chunk"; content: string }
  | { type: "tool_start"; tool: string; args: Record<string, any> }
  | { type: "tool_result"; tool_call: ToolCallData }
  | { type: "file_diff"; path: string; before: string; after: string; action: string }
  | { type: "shell_output"; command: string; chunk: string; exit_code: number | null; status: string }
  | { type: "todo_update"; items: TodoItemData[] }
  | { type: "files_modified"; paths: string[] }
  | { type: "deliverables"; deliverables: DeliverableSummary }
  | { type: "done"; intent?: string; metadata?: Record<string, any> }
  | { type: "error"; error: string }
  | { type: "overflow_warning"; summary?: string };

/** Callback interface for stream events */
export interface StreamCallbacks {
  onChunk: (content: string) => void;
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
    const port = await (window as any).aic?.getBackendStatus()?.then((s: any) => s.port).catch(() => 8000) || 8000;
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

  async cancel(message_id: string): Promise<void> {
    await apiClient.post("/chat/cancel", { message_id });
  },

  async regenerate(conversation_id: string, message_id: string): Promise<MessageRecord> {
    return apiClient.post<MessageRecord>("/chat/regenerate", { conversation_id, message_id });
  },

  async executeAgent(payload: {
    conversation_id: string;
    messages: { role: string; content: string }[];
    worker_role?: string;
  }, callbacks: {
    onChunk: (content: string) => void;
    onToolStart: (tool: string, args: Record<string, any>, callId: string) => void;
    onToolResult: (toolCall: ToolCallData) => void;
    onStatus: (status: string, data: any) => void;
    onDeliverables: (deliverables: DeliverableSummary) => void;
    onDone: (intent: string) => void;
    onError: (error: string) => void;
  }): Promise<() => void> {
    const port = await (window as any).aic?.getBackendStatus()?.then((s: any) => s.port).catch(() => 8000) || 8000;
    const url = `http://127.0.0.1:${port}/chat/execute`;
    const ac = new AbortController();

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
              case "done":
                callbacks.onDone(evt.intent || "");
                return;
              case "error":
                callbacks.onError(evt.error || "Unknown error");
                return;
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
