/**
 * Smoke E2E against the desktop FastAPI backend contract.
 * Run: node scripts/smoke-runtime.mjs
 */
const base = process.env.AIC_BASE_URL || "http://127.0.0.1:8000";
async function req(method, path, body) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  if (!res.ok) throw new Error(`${method} ${path} ${res.status}: ${text.slice(0, 200)}`);
  return data;
}

async function main() {
  console.log("base", base);
  const health = await req("GET", "/health");
  console.log("health", health.status, health.version);
  if (health.status !== "ok") throw new Error(`unexpected health status: ${health.status}`);

  const workers = await req("GET", "/runtime/workers");
  if (!Array.isArray(workers)) throw new Error("workers not array");
  console.log("workers", workers.length);
  if (!workers.every((worker) => worker.metrics)) throw new Error("worker metrics missing");

  const projects = await req("GET", "/projects");
  const activeProject = await req("GET", "/projects/active");
  console.log("projects", Array.isArray(projects) ? projects.length : projects);
  console.log("active project", activeProject?.name || "(none)");
  if (activeProject !== null && typeof activeProject !== "object") throw new Error("invalid active project response");

  const conv = await req("POST", "/conversations", { title: "AIC-ADE smoke" });
  const convId = conv.id;
  if (!convId) throw new Error("no conversation id");
  console.log("conversation", convId.slice(0, 12));

  const msg = await req("POST", `/conversations/${convId}/messages`, {
    role: "user",
    content: "Smoke persistence check.",
  });
  if (!msg.created_at) throw new Error("message timestamp missing");
  const messages = await req("GET", `/conversations/${convId}/messages`);
  if (!messages.some((item) => item.id === msg.id && item.created_at)) throw new Error("message history timestamp missing");
  console.log("message history", messages.length);

  const providers = await req("GET", "/providers");
  if (!Array.isArray(providers)) throw new Error("providers not array");
  console.log("providers", providers.length);

  console.log("SMOKE_OK");
}

main().catch((e) => {
  console.error("SMOKE_FAIL", e);
  process.exit(1);
});
