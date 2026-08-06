/**
 * Runtime client — thin wrapper around the AIC engine REST + WS endpoints.
 * This module provides a mutable `api` object whose base URL and token
 * are set at runtime via `configureClient`.
 */

import { setApiToken } from "./api/client";

let baseUrl = "http://127.0.0.1:8000";
let authToken = "";

export function configureClient(opts: { baseUrl: string; token: string | null }) {
  baseUrl = opts.baseUrl.replace(/\/$/, "");
  authToken = opts.token ?? "";
  // Keep the shared apiClient token in sync so the api/*.ts modules (providers,
  // conversations, jobs, etc.) also carry the per-install Bearer token.
  setApiToken(authToken || null);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  // In Electron the main process picks a free port (8000-8099) at startup —
  // resolve the real port dynamically so login/me hit the running backend.
  if (typeof window !== "undefined" && window.aic?.getBackendStatus) {
    try {
      const status = await window.aic.getBackendStatus();
      if (status && status.port) {
        baseUrl = `http://127.0.0.1:${status.port}`;
      }
    } catch {
      /* ignore */
    }
  }

  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };
  const options: RequestInit = { method, headers };
  if (body !== undefined) options.body = JSON.stringify(body);

  const res = await fetch(url, options);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      msg = errBody.detail || errBody.message || msg;
    } catch {
      try { msg = (await res.text()) || msg; } catch { /* ignore */ }
    }
    throw new Error(msg);
  }

  const text = await res.text();
  if (!text) return null as unknown as T;
  try { return JSON.parse(text); } catch { return text as unknown as T; }
}

// ── Public API surface ──────────────────────────────────────────

export const api = {
  health: () => request<{ status?: string; llm_configured?: boolean }>("GET", "/health"),
  me: () => request<unknown>("GET", "/auth/me"),
  login: (username: string, password: string) =>
    request<{ access_token: string; username?: string; user?: { username?: string } }>("POST", "/auth/login", { username, password }),

  listProviders: () => request<unknown[]>("GET", "/providers"),

  conversations: () => request<unknown[]>("GET", "/conversations"),
  messages: (convId: string) => request<unknown[]>("GET", `/conversations/${convId}/messages`),
  createConversation: (title: string) =>
    request<{ id: string; title?: string }>("POST", "/conversations", { title }),
  updateConversation: (convId: string, data: { title?: string }) =>
    request<unknown>("PATCH", `/conversations/${convId}`, data),
  deleteConversation: (convId: string) =>
    request<unknown>("DELETE", `/conversations/${convId}`),
  sendMessage: (convId: string, content: string) =>
    request<unknown>("POST", `/conversations/${convId}/messages`, { content }),

  workers: () => request<unknown[]>("GET", "/runtime/workers"),
  projects: () => request<unknown[]>("GET", "/projects"),
  tasks: (params?: { limit?: number }) => {
    const qs = params?.limit ? `?limit=${params.limit}` : "";
    return request<unknown[]>("GET", `/tasks${qs}`);
  },
  dashboard: () => request<unknown>("GET", "/dashboard"),
  createProject: (name: string, description: string) =>
    request<unknown>("POST", "/projects", { name, description }),

  getApprovalConfig: () =>
    request<{ mode: string; scope: Record<string, boolean>; risk_threshold: string }>("GET", "/approval-config"),
  updateApprovalConfig: (config: { mode?: string; scope?: Record<string, boolean>; risk_threshold?: string }) =>
    request<{ status: string }>("PUT", "/approval-config", config),
};

// ── WebSocket helper ────────────────────────────────────────────

export function connectWs(
  channel: string,
  onMessage: (msg: unknown) => void,
  onStatus: (status: string) => void,
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;

  function currentWsUrl(): string {
    const wsBase = baseUrl.replace(/^http/, "ws");
    // SECURITY: NEVER append the JWT as a query param (?token=...) — it can
    // leak into logs, proxies, and the browser history. The desktop backend
    // allows unauthenticated localhost connections (backend/routes/websocket.py
    // accepts localhost without a token), so no credential is sent on the wire.
    // TODO(auth): if localhost auth is ever required, pass the token via a
    // WebSocket subprotocol (new WebSocket(url, ["auth.jwt", token])) instead
    // of a query string.
    return `${wsBase}/ws/${channel}`;
  }

  async function connect() {
    if (closed) return;
    // Re-resolve the backend port before each (re)connect so a backend restart
    // onto a different port (8000-8099) doesn't leave the WS pinned to a dead
    // port forever.
    if (typeof window !== "undefined" && window.aic?.getBackendStatus) {
      try {
        const status = await window.aic.getBackendStatus();
        if (closed) return;
        if (status && status.port) {
          baseUrl = `http://127.0.0.1:${status.port}`;
        }
      } catch {
        /* ignore */
      }
    }
    try {
      ws = new WebSocket(currentWsUrl());
      ws.onopen = () => onStatus("connected");
      ws.onmessage = (ev) => {
        try { onMessage(JSON.parse(ev.data)); } catch { onMessage(ev.data); }
      };
      ws.onclose = () => {
        onStatus("disconnected");
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        onStatus("error");
        ws?.close();
      };
    } catch {
      onStatus("error");
    }
  }

  void connect();

  return () => {
    closed = true;
    ws?.close();
  };
}

// ── Streaming helper ────────────────────────────────────────────

export async function streamMessage(
  convId: string,
  content: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const url = `${baseUrl}/conversations/${convId}/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: JSON.stringify({ content }),
  });

  if (!res.ok) throw new Error(`Stream HTTP ${res.status}`);
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}

// ── Utility ─────────────────────────────────────────────────────

export function normalizeWorkspaceFiles(input: unknown): string[] {
  if (Array.isArray(input)) {
    return input.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const obj = item as Record<string, unknown>;
        return String(obj.path || obj.name || "");
      }
      return String(item);
    });
  }
  if (input && typeof input === "object") {
    const obj = input as Record<string, unknown>;
    if (Array.isArray(obj.files)) return normalizeWorkspaceFiles(obj.files);
  }
  return [];
}
