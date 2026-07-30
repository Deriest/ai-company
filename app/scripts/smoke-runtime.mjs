/**
 * Smoke E2E against live aic-platform using the same contract as AIC IDE runtimeClient.
 * Run: node scripts/smoke-runtime.mjs
 */
const base = process.env.AIC_BASE_URL || "http://127.0.0.1:8000";
const user = process.env.AIC_USER || "admin";
const pass = process.env.AIC_PASS || "admin123";

async function req(method, path, token, body, raw = false) {
  const headers = { Accept: raw ? "*/*" : "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (raw) {
    if (!res.ok) throw new Error(`${method} ${path} ${res.status}`);
    return res;
  }
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

const CANONICAL = [
  "hermes", "rex", "pm", "research", "designer", "documentation",
  "architect", "backend", "frontend", "qa", "performance",
  "database", "nexus", "flint", "security",
];

async function main() {
  console.log("base", base);
  const health = await req("GET", "/api/health");
  console.log("health", health.status, health.version);

  const login = await req("POST", "/api/auth/login", null, { username: user, password: pass });
  const token = login.access_token;
  if (!token) throw new Error("no access_token");
  console.log("login ok", login.username || user);

  const workers = await req("GET", "/api/workers", token);
  if (!Array.isArray(workers)) throw new Error("workers not array");
  console.log("workers", workers.length);
  const types = new Set(workers.map((w) => String(w.type || w.worker_type || "").toLowerCase()));
  const missing = CANONICAL.filter((id) => !types.has(id));
  if (missing.length) console.warn("missing canonical in API:", missing.join(", "));
  else console.log("canonical 15 present in API");
  const working = workers.filter((w) => String(w.status).toLowerCase() === "working");
  console.log("working now", working.map((w) => w.name || w.type).join(", ") || "(none)");

  const projects = await req("GET", "/api/projects", token);
  const tasks = await req("GET", "/api/tasks", token);
  console.log("projects", Array.isArray(projects) ? projects.length : projects);
  console.log("tasks", Array.isArray(tasks) ? tasks.length : tasks);

  if (Array.isArray(tasks) && tasks[0]?.id) {
    const tid = tasks[0].id;
    const detail = await req("GET", `/api/tasks/${tid}`, token);
    console.log("task detail", detail.id?.slice?.(0, 8) || tid.slice(0, 8), detail.status, detail.title);
    const deliv = await req("GET", `/api/tasks/${tid}/deliverables`, token);
    console.log("deliverables leases", Array.isArray(deliv.leases) ? deliv.leases.length : 0);
    const files = await req("GET", `/api/tasks/${tid}/workspace/files`, token);
    const fileList = Array.isArray(files) ? files : files?.files || [];
    console.log("workspace files", Array.isArray(fileList) ? fileList.length : typeof files);
    if (Array.isArray(fileList) && fileList.length) {
      const first = typeof fileList[0] === "string" ? fileList[0] : fileList[0].path || fileList[0].name;
      if (first) {
        const content = await req(
          "GET",
          `/api/tasks/${tid}/workspace/content?file=${encodeURIComponent(first)}`,
          token
        );
        console.log("file content bytes", String(content.content || "").length, "file", first);
      }
    }
    const zipRes = await req("GET", `/api/tasks/${tid}/download`, token, undefined, true);
    const buf = Buffer.from(await zipRes.arrayBuffer());
    console.log("zip bytes", buf.length, "ct", zipRes.headers.get("content-type"));
    if (buf.length < 20) throw new Error("zip too small");
  }

  const conv = await req("POST", "/api/conversations", token, { title: "aic-ide smoke" });
  const convId = conv.id;
  if (!convId) throw new Error("no conversation id");
  console.log("conversation", convId.slice(0, 12));

  const msg = await req("POST", `/api/conversations/${convId}/messages`, token, {
    content: "Status only — smoke test from AIC IDE. Do not create a large project.",
  });
  const reply = msg.response || msg.content || msg.message || JSON.stringify(msg).slice(0, 200);
  console.log("chat reply bytes", String(reply).length);
  console.log("chat preview", String(reply).slice(0, 160).replace(/\n/g, " "));

  try {
    const pending = await req("GET", "/api/approvals/pending", token);
    console.log("approvals pending", Array.isArray(pending) ? pending.length : typeof pending);
    const approvals = await req("GET", "/api/approvals", token);
    console.log("approvals total", Array.isArray(approvals) ? approvals.length : typeof approvals);
  } catch (e) {
    console.log("approvals skip", e.message || e);
  }

  try {
    const events = await req("GET", "/api/dashboard/events", token);
    const el = Array.isArray(events) ? events : events?.events;
    console.log("events", Array.isArray(el) ? el.length : typeof events);
  } catch (e) {
    console.log("events skip", e.message || e);
  }

  console.log("SMOKE_OK");
}

main().catch((e) => {
  console.error("SMOKE_FAIL", e);
  process.exit(1);
});
