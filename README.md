# AIC-ADE — Agentic Development Environment

**Latest release: v2.4.51** · **Electron + React 19** · **Python FastAPI + SQLite**

A local-first AI engineering desktop application with 15 specialized workers, durable conversations, real tool execution, a live office floor, and configurable model tiers.

## Download v2.4.51

| Platform | Download |
|---|---|
| Windows x64 | [AIC-ADE-Setup-2.4.51.exe](https://github.com/Deriest/ai-company/releases/download/v2.4.51/AIC-ADE-Setup-2.4.51.exe) |
| Linux AppImage | [AIC-ADE-2.4.51-linux-x86_64.AppImage](https://github.com/Deriest/ai-company/releases/download/v2.4.51/AIC-ADE-2.4.51-linux-x86_64.AppImage) |
| Linux Debian | [AIC-ADE-2.4.51-linux-amd64.deb](https://github.com/Deriest/ai-company/releases/download/v2.4.51/AIC-ADE-2.4.51-linux-amd64.deb) |

**[View release notes and all assets →](https://github.com/Deriest/ai-company/releases/tag/v2.4.51)**

### Checksums

SHA256 checksums are published in [`latest.json`](./latest.json) and [`SHA256SUMS`](./SHA256SUMS).

## Highlights

- **Command Center** — durable SQLite chat history; conversations survive navigation and app restarts.
- **Vision tier** — Thinker → Crafter → Sprinter → Vision. Attach files by drag-and-drop or file picker; images are sent as multimodal data to the selected Vision model.
- **Vision validation** — image requests are rejected with a clear message when the selected model does not support vision. Vision does not silently fall back to another tier.
- **15-worker office floor** — animated pixel-art workers, desks, status bubbles, progress bars, and activity log for Hermes, Rex, Aria, Sage, Luna, Echo, Atlas, Hugo, Leo, Eve, Pulse, Nova, Nexus, Flint, and Sentinel.
- **Real tool execution** — workers can read/write files, search codebases, run shell commands, and use configured MCP tools.
- **Auto-adaptive context** — context policies adapt to the selected model tier and window.
- **Automatic updates** — installed apps check [`latest.json`](https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json), download from GitHub Releases, verify SHA256, and install updates.
- **Global timezone support** — timestamps are stored in UTC and displayed in the user's local PC timezone.

## Architecture

```text
AI-Company/
├── app/                  # Electron + React desktop client
│   ├── src/main/         # Electron main process and updater
│   ├── src/renderer/     # React UI and Command Center
│   └── packaging/        # Bundled Python runtimes
├── backend/              # FastAPI backend and SQLite services
│   ├── backend/          # API routes, services, models
│   ├── agents/           # Worker definitions
│   ├── workers/          # Worker implementations
│   ├── llm/              # Provider and model-tier abstraction
│   └── storage/          # Conversation and message persistence
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

### Build and release

The release script builds Linux AppImage/deb and Windows NSIS x64, creates a GitHub Release, uploads artifacts, updates `latest.json` and checksums, then commits and pushes:

```bash
export GH_TOKEN=ghp_your_token
./scripts/release.sh 2.4.52
```

## Documentation

- [`docs/sot/`](./docs/sot/) — product and engineering Source of Truth
- [`docs/product-discovery/`](./docs/product-discovery/) — architecture and implementation analysis
- [`docs/archive/`](./docs/archive/) — historical QA notes and archived material

## License

Proprietary — TVD
