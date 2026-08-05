export interface ApiError {
  status: number;
  message: string;
}

export class ApiClientError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiClientError";
  }
}

// M4: cache the resolved backend URL for a short TTL. Previously EVERY REST
// call did an IPC getBackendStatus round-trip, whose main-process handler runs
// a real fetch(/health) — so each API call cost an extra HTTP hop. A backend
// restart onto a different port (8000-8099) is picked up within the TTL, and
// network errors invalidate the cache immediately.
const URL_CACHE_TTL_MS = 30_000;
let cachedBaseUrl: string | null = null;
let cachedBaseUrlAt = 0;

export function invalidateBaseUrlCache(): void {
  cachedBaseUrl = null;
  cachedBaseUrlAt = 0;
}

async function resolveBaseUrl(): Promise<string> {
  if (cachedBaseUrl && Date.now() - cachedBaseUrlAt < URL_CACHE_TTL_MS) {
    return cachedBaseUrl;
  }
  let port = 8000;
  if (typeof window !== "undefined" && window.aic?.getBackendStatus) {
    port = await window.aic.getBackendStatus().then((s) => s.port).catch(() => 8000) || 8000;
  }
  cachedBaseUrl = `http://127.0.0.1:${port}`;
  cachedBaseUrlAt = Date.now();
  return cachedBaseUrl;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(`${await resolveBaseUrl()}${suffix}`, options);
  } catch {
    // M4: network failure — the backend may have restarted on a new port.
    // Invalidate the cache and re-resolve once before throwing.
    invalidateBaseUrlCache();
    try {
      res = await fetch(`${await resolveBaseUrl()}${suffix}`, options);
    } catch {
      let backendInfo = "";
      try {
        const status = await window.aic?.getBackendStatus?.();
        if (status?.error) backendInfo = ` Backend error: ${status.error}`;
        if (status?.logFile) backendInfo += ` (Log: ${status.logFile})`;
      } catch { /* ignore */ }
      throw new ApiClientError(0, `Network error. Is the backend running?${backendInfo}`);
    }
  }

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      msg = errBody.detail || errBody.message || msg;
    } catch {
      try {
        msg = await res.text() || msg;
      } catch {
        /* ignore */
      }
    }
    throw new ApiClientError(res.status, msg);
  }

  // Handle empty responses
  const text = await res.text();
  if (!text) return null as unknown as T;
  
  try {
    return JSON.parse(text);
  } catch {
    return text as unknown as T;
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
