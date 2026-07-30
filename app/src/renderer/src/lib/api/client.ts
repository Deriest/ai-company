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

let baseUrl = "http://127.0.0.1:8000";

export function setApiBaseUrl(url: string) {
  baseUrl = url;
}

export function getApiBaseUrl() {
  return baseUrl;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  // If we're in Electron, fetch dynamic port
  if (typeof window !== "undefined" && window.aic?.getBackendStatus) {
    try {
      const status = await window.aic.getBackendStatus();
      if (status && status.port) {
        setApiBaseUrl(`http://127.0.0.1:${status.port}`);
      }
    } catch {
      /* ignore */
    }
  }

  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  const options: RequestInit = {
    method,
    headers,
  };

  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(url, options);
  } catch (err) {
    // Try to get backend status for better error message
    let backendInfo = "";
    try {
      if (window.aic?.getBackendStatus) {
        const status = await window.aic.getBackendStatus();
        backendInfo = status.error ? ` Backend error: ${status.error}` : "";
        if (status.logFile) backendInfo += ` (Log: ${status.logFile})`;
      }
    } catch { /* ignore */ }
    throw new ApiClientError(0, `Network error. Is the backend running?${backendInfo}`);
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
