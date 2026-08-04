# AIC-ADE — Agentic Development Environment

**Latest release: v2.4.65** · **Electron + React 19** · **Python FastAPI + SQLite**

A self-hosted, local-first AI engineering desktop application with specialized workers, durable conversations, real tool execution, a live office floor, configurable model tiers, and a full plugin system.

## Privacy and data ownership

**Your data stays on your machine.** AIC-ADE runs its backend locally (bound to `127.0.0.1`) and stores chat history, projects, API keys, skills, plugins, and SQLite data in the local application data directory. The developer/maintainer does not have access to your files, conversations, projects, or provider credentials. Network requests are made only to services you configure (for example, your LLM provider, GitHub when you explicitly install a skill/plugin or open a report, and GitHub Releases for update downloads).

A per-install random credential is generated on first launch and stored with restrictive permissions (`0600`); the built-in `/auth/login` and `/auth/me` endpoints use it. Bug reports open a pre-filled GitHub Issue in your browser — nothing is submitted automatically.

## Download v2.4.65

| Platform | Download |
|---|---|
| Windows x64 | [AIC-ADE-Setup-2.4.65.exe](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-Setup-2.4.65.exe) |
| Linux AppImage | [AIC-ADE-2.4.65-linux-x86_64.AppImage](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-2.4.65-linux-x86_64.AppImage) |
| Linux Debian | [AIC-ADE-2.4.65-linux-amd64.deb](https://github.com/Deriest/ai-company/releases/download/v2.4.65/AIC-ADE-2.4.65-linux-amd64.deb) |

**[View release notes and all assets →](https://github.com/Deriest/ai-company/releases/tag/v2.4.65)**

### Checksums

SHA256 checksums are published in [`latest.json`](./latest.json) and [`SHA256SUMS`](./SHA256SUMS).

## Highlights

- **Command Center** — durable SQLite chat history; conversations survive navigation and app restarts.
- **Model tiers** — Thinker → Crafter → Sprinter → Vision. Attach files by drag-and-drop or file picker; images are sent as multimodal data to the selected Vision model, and requests are rejected with a clear message when the selected model does not support vision.
- **Plugin system** — install plugins from GitHub (`POST /plugins/install`), with commands, agent instructions, MCP servers, and skills activated per worker. Update endpoint (`POST /plugins/{id}/update`) and "install to all" support included.
- **Skills** — install GitHub skill packages (SKILL.md manifest) scoped to worker roles.
- **Real tool execution** — workers can read/write files, search codebases, run shell commands, and use configured MCP tools (any stdio/HTTP/SSE endpoint; local desktop app, no allowlist restriction).
- **Auto-adaptive context** — context policies adapt to the selected model tier and real context window (catalog-aware).
- **Live office floor** — animated pixel-art workers with status bubbles, progress bars, and activity log.
- **Automatic updates** — installed apps check [`latest.json`](https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json), download from GitHub Releases, verify SHA256, and install. Mandatory/minimum-version updates are enforced.
- **Production hardening** — structured logging with trace IDs, request validation middleware, self-healing startup, job scheduler, rate limiting, metrics, atomic state writes, single-instance lock, navigation allowlist, and streamed chat (first token in ~1s, not after full generation).

## Architecture

```text
AI-Company/
├── app/                  # Electron + React desktop client
│   ├── src/main/         # Electron main process, updater, security
│   ├── src/renderer/     # React UI and Command Center
│   └── packaging/        # Bundled Python runtimes
├── backend/              # FastAPI backend and SQLite services
│   ├── backend/          # API routes, services, models
│   ├── agents/           # Worker definitions
│   ├── workers/          # Worker implementations
│   ├── llm/              # Provider and model-tier abstraction
│   ├── storage/          # Conversation and message persistence
│   └── tests/            # 785+ pytest tests (isolated DB via conftest)
├── docs/                 # Source of Truth and architecture docs
└── scripts/              # Release and utility scripts
```

## Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Wine for Windows cross-builds on Linux
- `GH_TOKEN` for releases

### Run locally

```bash
cd app
npm install
npm run dev
```

Backend runs on `127.0.0.1:8000` (or a free port in 8000–8099). The renderer discovers the real port automatically.

### Build and release

The release script builds Linux AppImage/deb and Windows NSIS x64, creates a GitHub Release, uploads artifacts, updates `latest.json` and checksums, then commits and pushes:

```bash
export GH_TOKEN=ghp_your_token
./scripts/release.sh 2.4.66
```

## Tests

```bash
# Backend (isolated temp DB — no interference with live data)
cd backend && .venv/bin/python -m pytest tests/ -q

# Frontend
cd app && npx vitest run && npx tsc -b
```

## Documentation

- [`docs/sot/`](./docs/sot/) — product and engineering Source of Truth
- [`docs/product-discovery/`](./docs/product-discovery/) — architecture and implementation analysis
- [`docs/archive/`](./docs/archive/) — historical QA notes and archived material
- [`CHANGELOG.md`](./CHANGELOG.md) — release history

## License

Proprietary — TVD