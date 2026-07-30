/** Internal desktop session credentials — not user-facing.
 *
 * AIC ADE runs a local sidecar engine that ships with a default admin
 * identity. The desktop app auto-authenticates silently — users never
 * see or type these credentials. They are intentionally inline (not in
 * env vars) because the sidecar is embedded, not a remote service.
 */
export const DESKTOP_IDENTITY = {
  username: "admin",
  password: "admin123",
} as const;

export const ENGINE_PORT = 8000;
export const INTERNAL_ENGINE_URL = `http://127.0.0.1:${ENGINE_PORT}`;
