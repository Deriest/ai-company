# AIC-ADE — Agentic Development Environment

**Latest release: v2.4.65** · **Electron + React 19** · **Python FastAPI + SQLite** · **Local-first**

AIC-ADE is a self-hosted, local-first AI engineering desktop application. It runs a
FastAPI backend on your machine (bound to `127.0.0.1`), provides a fully offline
Command Center for chat, and delivers real tool execution, a live office floor of
specialized AI workers, configurable model tiers, a plugin/skill system, and
automatic updates — all without your data leaving your computer.

---

## Table of Contents

- [Privacy & data ownership](#privacy-and-data-ownership)
- [Download](#download-v2465)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [LLM Providers](#llm-providers)
  - [Model Tiers](#model-tiers)
  - [Vision](#vision)
- [Plugins & Skills](#plugins--skills)
- [Architecture](#architecture)
- [Development](#development)
- [Testing](#testing)
- [Build & Release](#build--release)
- [Security](#security)
- [Documentation](#documentation)
- [License](#license)

---

## Privacy and data ownership

**Your data stays on your machine.** AIC-ADE runs its backend locally on
`127.0.0.1` and stores chat history, projects, API keys, skills, plugins, and
SQLite data in your local application data directory. The developer/maintainer
has no access to your files, conversations, projects, or provider credentials.

Network requests are made **only** to services you configure:

- your LLM provider (OpenAI-compatible)
- GitHub, when you explicitly install a skill or plugin, or open a report
- GitHub Releases, for automatic update checks and downloads

A **per-install random credential** is generated on first launch, stored with
restrictive permissions (`0600`), and used by the built-in `/auth/login` and
`/auth/me` endpoints. Bug reports open a pre-filled GitHub Issue in your
browser — nothing is submitted automatically; review before clicking submit.

---

## Download v2.4.65

| Platform | Download |
|---|---|
| Windows x64 | [AIC-ADE-Setup-2.4.65.exe](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-Setup-2.4.65.exe) |
| Linux AppImage | [AIC-ADE-2.4.65-linux-x86_64.AppImage](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-2.4.65-linux-x86_64.AppImage) |
| Linux Debian | [AIC-ADE-2.4.65-linux-amd64.deb](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-2.4.65-linux-amd64.deb) |

**View all release notes and assets →** [GitHub Releases](https://github.com/Deriest/ai-company/releases/tag/v2.4.65)

### Checksums

SHA256 checksums for every artifact are published in
[`latest.json`](./latest.json) and [`SHA256SUMS`](./SHA256SUMS). The automatic
updater verifies the SHA256 of every downloaded artifact before installing.

---

## Features

### Command Center
- Durable SQLite chat history — conversations survive navigation and app restarts.
- Streaming responses (first token arrives in ~1s, not after full generation).
- Tool calls, file diffs, and shell output streamed inline via SSE.
- Search, conversation archive, and conversation restore.

### Model Tiers
- **Thinker → Crafter → Sprinter → Vision** — pick a distinct model per tier.
- Attach files by drag-and-drop or file picker; images are sent as multimodal
  data to the selected Vision model.
- Vision validation: requests are rejected with a clear message when the
  selected model does not support vision — no silent fallback.
- Auto-adaptive context: token budgets adapt to the selected model tier and its
  real context window (catalog-aware, 16k–1M+).

### Real Tool Execution
Specialized workers can execute real tools during a task:
- `read_file` / `write_file` — line-based, workspace-scoped (path traversal blocked)
- `explore` / `search` — codebase navigation and pattern search
- `shell` — permission-gated command execution with timeout control
- `mcp_call` — calls any configured MCP server tool

### 15-Worker Office Floor
Animated pixel-art workers with status bubbles, progress bars, and an activity
log: **Hermes, Rex, Aria, Sage, Luna, Echo, Atlas, Hugo, Leo, Eve, Pulse, Nova,
Nexus, Flint, Sentinel** — each with a specialized role across Leadership,
Product, Engineering, and Platform departments.

### Plugins & Skills
- **Plugins** — install from any public GitHub repo (`POST /plugins/install`).
  Plugins can ship commands, agent instructions, MCP servers, and skills that
  activate per worker role. Update in place (`POST /plugins/{id}/update`),
  "install to all" shortcut, enable/disable, and clean uninstall.
- **Skills** — install GitHub skill packages (SKILL.md manifest) scoped to
  worker roles, resolved at runtime for both the interactive agent and the
  company batch runtime.

### Automatic Updates
- Installed apps poll [`latest.json`](https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json).
- Downloads are verified against SHA256 and install cleanly (AppImage/deb/NSIS).
- `minimumVersion` and `mandatory` updates are enforced — mandatory updates
  cannot be dismissed.

### Production Hardening
- Structured logging with per-request `trace_id` + request metrics.
- Request validation middleware (body-size cap, SQL-pattern checks).
- Self-healing startup, job scheduler, rate limiting, and metrics endpoints.
- Atomic state writes, single-instance lock, navigation allowlist, crash handlers.
- Streaming messages are finalized on client disconnect (no stuck rows).

---

## Quick Start

### From the release build

1. Download the installer for your platform (see [Download](#download-v2465)).
2. Install and launch.
3. Open **Settings → Providers** and add your LLM provider (any OpenAI-compatible
   endpoint: OpenAI, OpenRouter, vLLM, Ollama, LM Studio, etc.).
4. Start chatting, or create a task and watch the office floor work.

### From source

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# set your provider (see Configuration)
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 2. Frontend (separate terminal)
cd app
npm install
npm run dev
```

The backend listens on `127.0.0.1:8000` (or a free port in 8000–8099); the
renderer discovers the real port automatically.

---

## Configuration

### LLM Providers

| Method | Where |
|---|---|
| GUI | **Settings → Providers** → Add Provider (name, base URL, API key, model list) |
| Environment | `AIC_LLM_BASE_URL`, `AIC_LLM_API_KEY`, `AIC_LLM_THINKER`, `AIC_LLM_CRAFTER`, `AIC_LLM_SPRINTER`, `AIC_LLM_VISION` |

Providers are stored per-provider (encrypted API keys at rest), and the engine
config you set in Settings takes priority over auto-picked models.

### Model Tiers

Configure a model per tier in **Settings → Providers**. The engine:

1. Uses your explicit engine config (`AIC_MODEL_*`) first.
2. Falls back to the provider's model list (filtering out known-internal
   entries like `combo/` and `iamhc/`).
3. Falls back to worker runtime assignments.

If a tier has no configured model, the agent surfaces a clear error instead of
silently failing.

### Vision

Attach an image and the request is routed to the **Vision** tier. If the
selected model cannot accept images, AIC-ADE rejects the request with a clear
message — it never silently re-routes to a text-only tier.

---

## Plugins & Skills

### Install a plugin

```bash
# From the UI: Plugins view → Install Plugin → paste a GitHub URL
#   https://github.com/<owner>/<repo>            (repo root)
#   https://github.com/<owner>/<repo>/tree/<branch>/<path>   (subdirectory)
```

A plugin can provide:

- `commands/*.{sh,py,js}` → exposed as callable tools for assigned workers
- `agents/*.md` / `SKILL.md` → injected as agent instructions
- `mcp/*.json` → MCP servers registered and connected at activation
- `manifest` (`.claude-plugin/marketplace.json` or `plugin.json`) → metadata

After install, assign the plugin to one or more workers (or "all"). Plugin
commands are auto-granted to assigned workers. MCP servers declared by a plugin
are registered and connected (local desktop app — any stdio/HTTP/SSE endpoint
is allowed).

### Install a skill

```bash
# From the UI: Skills view → Install from GitHub → paste a repo URL
```

Skills are parsed from a `SKILL.md` manifest (frontmatter) and scoped to worker
roles. They are resolved at runtime and injected into the task context.

---

## Architecture

```text
AI-Company/
├── app/                      # Electron + React 19 desktop client
│   ├── src/main/             # Electron main process, updater, security
│   ├── src/renderer/         # React UI and Command Center
│   ├── src/preload/          # IPC bridge (window.aic)
│   ├── src/shared/           # Shared types/logic (update manifest, version)
│   └── packaging/            # Bundled Python runtimes
├── backend/                  # FastAPI backend + SQLite
│   ├── backend/              # API routes, services, models
│   │   ├── api/routes/       # chat, providers, plugins, skills, mcp, rag, ...
│   │   ├── services/         # agent_runner, chat_service, tool_executor, ...
│   │   ├── middleware/       # validation, logging, metrics, rate limit
│   │   └── migrations/       # schema migrations (idempotent, verified)
│   ├── agents/               # Worker definitions
│   ├── workers/              # Worker implementations (tools, base)
│   ├── llm/                  # Provider abstraction, model tiers, catalog
│   ├── conversation/         # LLM chat engine
│   ├── workflow/             # FSM: 8 phases + approval gates
│   ├── storage/              # Conversation & message persistence
│   └── tests/                # 785+ pytest tests (isolated DB via conftest)
├── docs/                     # Source of Truth (docs/sot) + archive
├── scripts/                  # release.sh, download_server.py
├── CHANGELOG.md              # Full release history
├── latest.json               # Auto-update manifest
└── SHA256SUMS                # Artifact checksums
```

### Backend → renderer flow

```
React renderer ──IPC──▶ Electron main ──spawn──▶ FastAPI backend (127.0.0.1)
      ▲                                                  │
      └────────────── SSE (chat/stream) ◀────────────────┘
```

---

## Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Wine (only for Windows cross-builds on Linux)
- `GH_TOKEN` (only for releases)

### Run locally

```bash
cd app
npm install
npm run dev
```

### Project layout conventions

- New API routes → `backend/backend/api/routes/`
- New services → `backend/backend/services/`
- New models → `backend/backend/models/` (SQLAlchemy) / `backend/storage/`
- New renderer views → `app/src/renderer/src/components/`
- New tests → `backend/tests/` (backend) / `app/src/renderer/src/lib/*.test.ts` (frontend)

---

## Testing

```bash
# Backend — full suite (isolated temp DB, no interference with live data)
cd backend
.venv/bin/python -m pytest tests/ -q       # 785 passed, 0 failed

# Frontend — unit tests + type check + lint
cd app
npx vitest run                              # 98 passed
npx tsc -b                                 # exit 0
npx oxlint src                             # 0 warnings
```

Coverage highlights: plugin engine (install/update/escape/isolate), tool
executor (path traversal, default-deny permissions), MCP client (stdio/HTTP,
JSON-RPC), agent runner (tool loop, stuck-loop detection, feedback), SSE parser
(chat.ts), context builder, taste checker, and regression suites.

---

## Build & Release

`scripts/release.sh` automates the whole pipeline:

1. Bump the version in `package.json` + `package-lock.json`.
2. Build Linux (AppImage + deb) and Windows (NSIS x64).
3. Create the GitHub Release and upload all three artifacts.
4. Update `latest.json` + `SHA256SUMS` (root and `app/release/`).
5. Commit and push.

```bash
export GH_TOKEN=ghp_your_token
./scripts/release.sh 2.4.66
```

Installed apps auto-detect the new release via `latest.json` and prompt to
download + install.

---

## Security

- **Loopback-only backend** — binds to `127.0.0.1`; non-loopback traffic is
  rejected by middleware.
- **Per-install credential** — random secret generated at first launch, stored
  `0600`, used by `/auth/login` + `/auth/me`.
- **Path traversal protection** — every file tool resolves paths against the
  workspace root (`commonpath` + separator-boundary checks).
- **Path boundary checks** — plugin/skill installs use `relative_to`; sibling
  prefix bypasses are rejected.
- **SSRF guard** — `web_fetch` blocks private/loopback/link-local targets and
  re-validates redirects.
- **Tool allowlist** — `/tools/execute` accepts only known tool names.
- **Default-deny permissions** — unknown worker types get a minimal read-only
  tool set; plugin tools are auto-granted only to assigned workers.
- **Navigation allowlist** — the Electron window only navigates to the app's
  own `dist` bundle; `file://` and external navigation are blocked.
- **CSP** — strict `default-src 'self'`; `connect-src` limited to `127.0.0.1:*`.
- **Encrypted API keys at rest** — provider keys are encrypted before storage.
- **Single-instance lock** — prevents duplicate backends/DB lock contention.

---

## Documentation

- [`docs/sot/`](./docs/sot/) — product and engineering Source of Truth (constitution, architecture, specs)
- [`docs/product-discovery/`](./docs/product-discovery/) — architecture and implementation analysis
- [`docs/archive/`](./docs/archive/) — historical QA notes and archived material
- [`CHANGELOG.md`](./CHANGELOG.md) — full release history (v2.4.6 → v2.4.65)

---

## License

Proprietary — TVD