# AIC-ADE — Agentic Development Environment

**Latest release: v2.6.28** · **Electron + React 19** · **Python FastAPI + SQLite** · **Local-first**

AIC-ADE is a self-hosted, local-first AI engineering desktop application. It runs a
FastAPI backend on your machine (bound to `127.0.0.1`), provides a fully offline
Command Center for chat, and delivers real tool execution, a live office floor of
specialized AI workers, configurable model tiers, a plugin/skill system, and
automatic updates — all without your data leaving your computer.

---

## Table of Contents

- [Privacy & data ownership](#privacy-and-data-ownership)
- [Download](#download-v2628)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [LLM Providers](#llm-providers)
  - [Model Tiers](#model-tiers)
  - [Vision](#vision)
  - [Workspace folders](#workspace-folders)
- [Plugins & Skills](#plugins--skills)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
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

## Download v2.6.28

| Platform | Download |
|---|---|
| Windows x64 | [AIC-ADE-Setup-2.6.28.exe](https://github.com/Deriest/ai-company/releases/download/v2.6.28/AIC-ADE-Setup-2.6.28.exe) |
| Linux AppImage | [AIC-ADE-2.6.28-linux-x86_64.AppImage](https://github.com/Deriest/ai-company/releases/download/v2.6.28/AIC-ADE-2.6.28-linux-x86_64.AppImage) |
| Linux Debian | [AIC-ADE-2.6.28-linux-amd64.deb](https://github.com/Deriest/ai-company/releases/download/v2.6.28/AIC-ADE-2.6.28-linux-amd64.deb) |

**View all release notes and assets →** [GitHub Releases](https://github.com/Deriest/ai-company/releases/tag/v2.6.28)

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

1. Download the installer for your platform (see [Download](#download-v2628)).
2. Install and launch.
3. Open **Settings → Providers** and add your LLM provider (any OpenAI-compatible
   endpoint: OpenAI, OpenRouter, vLLM, Ollama, LM Studio, etc.).
4. Start chatting, or create a task and watch the office floor work.

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

### Workspace folders

AIC-ADE always works in a specific folder on your computer. When you create a
task, the AI relies on remembering the folder it used last time, the project
you've selected, or simply asks you which folder to use:

1. **Project folder** — if you've already chosen a project for the conversation,
   that project's folder is used.
2. **Last used folder** — if no project is pinned, AIC-ADE uses the last folder
   you worked in (a "remember last used" convenience).
3. **Ask you** — if neither applies, AIC-ADE asks which folder to use before it
   starts writing any files.

The folder that will be used is always shown in the chat before the agent starts
working, so you can confirm it's the right one. To change it, just tell AIC-ADE
the new folder path. This prevents files from being written to the wrong place.

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

## What's New in v2.6.28

### Security Vulnerability Fixes
- **Ed25519 signature verification**: Fixed critical bypass in update manifest signing (RFC 7517 compliant base64url encoding)
- **CI pipeline integrity**: Removed test failure masking — quality gates now properly enforced
- **Complete test coverage**: All 1160+ tests now discovered and running

### Infrastructure Improvements
- Test infrastructure hardening (~53 bugs resolved): missing imports, schema mismatches, credential issues, fail-stop logic
- Complete test suite green: 848 passed, 1 skipped (99.9% pass rate)
- Runtime executor status keys enhanced for better lifecycle tracking

### Production Hardening
All code review findings from comprehensive security audit addressed:
- Authentication bypass prevention
- Signature verification correctness  
- Quality gate enforcement

---

## Tips & Best Practices

- **Be specific** — the more detail you give about what you want and where it
  should go, the better the result.
- **Confirm the folder** — before a task starts, AIC-ADE shows the folder it
  will work in. Make sure it's the right one; you can change it by telling the
  assistant the new path.
- **Attach files** — drag and drop images or files to give the AI context; images
  are analyzed by your Vision model.
- **Use projects** — organize related work into projects to keep tasks and
  history together.

## Troubleshooting

### "No provider configured"
Open **Settings → Providers** and add your LLM provider (any OpenAI-compatible
endpoint: OpenAI, OpenRouter, vLLM, Ollama, LM Studio, etc.) before chatting.

### Slow responses
- Check your internet connection.
- Verify provider status in **Settings → Providers**.
- Try a different provider or model, or set a lower reasoning level.

### The app writes files to the wrong folder
AIC-ADE always shows the folder it will use before starting. If it's wrong, tell
the assistant the correct folder path, or select the right project first.

### Application won't start
- Ensure no other instance is running.
- Check system requirements (see below).
- Review logs in the application data directory.

### Where is my data stored?
Everything is stored locally on your machine in the application data directory.
Your files, chat history, and provider keys never leave your computer.

## System Requirements

- **OS**: Windows 10+, macOS 10.15+, Ubuntu 20.04+
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 500MB free space
- **Network**: Internet for AI provider access

---

## Security

Your security and privacy are built in:

- **Runs only on your computer** — the app binds to `127.0.0.1` (localhost) and
  does not expose itself to your network.
- **Local storage** — chat history, projects, and settings live only on your
  machine. Provider API keys are encrypted before being stored.
- **No background data collection** — the app only talks to services you
  configure (your AI provider, and GitHub when you install a skill/plugin or
  check for updates).
- **Safe file handling** — the AI can only read and write files inside the
  folder you've chosen; it cannot escape that folder.
- **Clear navigation** — the app only opens its own interface and a few
  trusted links (e.g. GitHub), never arbitrary web pages.
- **One instance at a time** — the app prevents duplicate backends that could
  cause data conflicts.
- **Enhanced security posture** — Comprehensive security hardening applied:
  - All authentication endpoints use `Cache-Control: no-store` to prevent credential caching
  - Content Security Policy (CSP) with strict source restrictions
  - Permissions policy to disable unnecessary browser features
  - Cross-domain policies set to `none`
  - Legacy encryption keys loaded from environment variables instead of hardcoded
  - Startup fails completely if default credentials would be used (no insecure fallback)
  - GitHub token validation ensures proper format before storage
  - Ed25519 signature verification fixed (RFC 7517 compliant)

---

## Documentation

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — system architecture
- [`docs/PRODUCT.md`](./docs/PRODUCT.md) — product specifications
- [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md) — development guidelines
- [`docs/TESTING.md`](./docs/TESTING.md) — testing strategy
- [`docs/SECURITY.md`](./docs/SECURITY.md) — security documentation
- [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — deployment procedures
- [`CHANGELOG.md`](./backend/CHANGELOG.md) — backend release history

---

## License

Proprietary — TVD
