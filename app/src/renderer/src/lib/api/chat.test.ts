import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { chatApi } from "./chat";

/**
 * SSE parser tests. We mock `fetch` with a ReadableStream of SSE payloads
 * (including split-across-chunk boundaries) and verify event dispatch.
 */

function mockFetchWithSSE(chunks: string[]) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) {
        controller.enqueue(encoder.encode(c));
      }
      controller.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body: stream }));
}

async function flush() {
  // Let the async fetch/read loop settle.
  await new Promise((r) => setTimeout(r, 20));
}

beforeEach(() => {
  (globalThis as any).window = {
    aic: {
      getBackendStatus: vi.fn().mockResolvedValue({ port: 8000 }),
    },
  };
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (globalThis as any).window;
});

describe("executeAgent SSE parser", () => {
  it("dispatches chunk / tool_start / tool_result / done events", async () => {
    const sse = [
      'data: {"type":"status","status":"thinking"}\n\n',
      'data: {"type":"chunk","content":"hello"}\n\n',
      'data: {"type":"tool_start","tool":"read_file","args":{"path":"a.py"},"call_id":"c1"}\n\n',
      'data: {"type":"tool_result","tool_call":{"id":"c1","type":"read_file","label":"Read","status":"completed","output":"x"}}\n\n',
      'data: {"type":"done","intent":"finish"}\n\n',
    ].join("");
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onStatus).toHaveBeenCalledWith("thinking", expect.anything());
    expect(callbacks.onChunk).toHaveBeenCalledWith("hello");
    expect(callbacks.onToolStart).toHaveBeenCalledWith("read_file", { path: "a.py" }, "c1");
    expect(callbacks.onToolResult).toHaveBeenCalledWith(
      expect.objectContaining({ id: "c1", status: "completed" }),
    );
    expect(callbacks.onDone).toHaveBeenCalledWith("finish");
    expect(callbacks.onError).not.toHaveBeenCalled();
  });

  it("handles events split across multiple stream chunks", async () => {
    const chunk1 = 'data: {"type":"chunk","content":"par';
    const chunk2 = 'tial"}\n\ndata: {"type":"done","intent":"ok"}\n\n';
    mockFetchWithSSE([chunk1, chunk2]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onChunk).toHaveBeenCalledWith("partial");
    expect(callbacks.onDone).toHaveBeenCalledWith("ok");
  });

  it("dispatches error events and stops", async () => {
    const sse = 'data: {"type":"error","error":"boom"}\n\n';
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onError).toHaveBeenCalledWith("boom");
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });

  it("dispatches cancelled events as a status and never fires done", async () => {
    const sse = 'data: {"type":"cancelled","reason":"User cancelled"}\n\n';
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    // The cancelled event must be forwarded as a status (so ChatView can keep
    // its *[stopped]* marker) and must terminate the stream — a fallthrough
    // would let the later onDone("") overwrite the partial content.
    expect(callbacks.onStatus).toHaveBeenCalledWith(
      "cancelled",
      expect.objectContaining({ type: "cancelled", reason: "User cancelled" }),
    );
    expect(callbacks.onDone).not.toHaveBeenCalled();
    expect(callbacks.onError).not.toHaveBeenCalled();
  });

  it("dispatches overflow_warning through onStatus without terminating", async () => {
    const sse = [
      'data: {"type":"overflow_warning","estimated":9000,"budget":8000}\n\n',
      'data: {"type":"chunk","content":"still going"}\n\n',
      'data: {"type":"done","intent":"ok"}\n\n',
    ].join("");
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onStatus).toHaveBeenCalledWith(
      "overflow_warning",
      expect.objectContaining({ type: "overflow_warning" }),
    );
    // The warning is mid-stream: the stream must continue to the done event.
    expect(callbacks.onChunk).toHaveBeenCalledWith("still going");
    expect(callbacks.onDone).toHaveBeenCalledWith("ok");
  });

  it("dispatches the clarify event with its full payload and keeps streaming to done", async () => {
    const sse = [
      'data: {"type":"clarify","data":{"reason":"Missing project","questions":[{"id":"proj","question":"Which project?","options":["blog","api"]},{"id":"lang","question":"Language?"}]}}\n\n',
      'data: {"type":"done","intent":"clarified"}\n\n',
    ].join("");
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
      onDeliverables: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onClarify: vi.fn(),
    };

    await chatApi.executeAgent({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    // The clarify payload must be forwarded whole (reason + questions + options)…
    expect(callbacks.onClarify).toHaveBeenCalledWith({
      reason: "Missing project",
      questions: [
        { id: "proj", question: "Which project?", options: ["blog", "api"] },
        { id: "lang", question: "Language?" },
      ],
    });
    // …and the stream must NOT terminate on clarify — a later done event
    // finalizes the assistant message (no dead-end thinking state).
    expect(callbacks.onDone).toHaveBeenCalledWith("clarified");
    expect(callbacks.onError).not.toHaveBeenCalled();
  });
});

describe("streamWithTools SSE parser", () => {
  it("dispatches chunk / tool_start / shell_output / done events", async () => {
    const sse = [
      'data: {"type":"chunk","content":"x"}\n\n',
      'data: {"type":"tool_start","tool":"run_shell","args":{"command":"ls"}}\n\n',
      'data: {"type":"shell_output","command":"ls","chunk":"a.txt","exit_code":0,"status":"running"}\n\n',
      'data: {"type":"done"}\n\n',
    ].join("");
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onRewrite: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onFileDiff: vi.fn(),
      onShellOutput: vi.fn(),
      onTodoUpdate: vi.fn(),
      onFilesModified: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.streamWithTools({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onChunk).toHaveBeenCalledWith("x");
    expect(callbacks.onToolStart).toHaveBeenCalledWith("run_shell", { command: "ls" });
    expect(callbacks.onShellOutput).toHaveBeenCalledWith(
      expect.objectContaining({ command: "ls", chunk: "a.txt", exit_code: 0 }),
    );
    expect(callbacks.onDone).toHaveBeenCalled();
    expect(callbacks.onError).not.toHaveBeenCalled();
  });

  it("recognizes the [DONE] sentinel", async () => {
    const sse = 'data: {"type":"chunk","content":"last"}\n\ndata: [DONE]\n\n';
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onRewrite: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onFileDiff: vi.fn(),
      onShellOutput: vi.fn(),
      onTodoUpdate: vi.fn(),
      onFilesModified: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.streamWithTools({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onChunk).toHaveBeenCalledWith("last");
    expect(callbacks.onDone).toHaveBeenCalled();
  });

  it("dispatches error events", async () => {
    const sse = 'data: {"type":"error","error":"rate limited"}\n\n';
    mockFetchWithSSE([sse]);

    const callbacks = {
      onChunk: vi.fn(),
      onRewrite: vi.fn(),
      onToolStart: vi.fn(),
      onToolResult: vi.fn(),
      onFileDiff: vi.fn(),
      onShellOutput: vi.fn(),
      onTodoUpdate: vi.fn(),
      onFilesModified: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatApi.streamWithTools({ conversation_id: "c", messages: [] }, callbacks);
    await flush();

    expect(callbacks.onError).toHaveBeenCalledWith("rate limited");
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });
});