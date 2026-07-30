# AIC-ADE — Agentic Development Environment

**Version:** 2.4.0  
**Category:** Agentic Development Environment (ADE)  
**Runtime:** Python FastAPI + SQLite  
**Desktop Client:** Electron + React 19  

---

## Architecture Overview

AIC-ADE is a local-first AI engineering platform designed for autonomous software development. No data leaves the host machine — all API keys, source code, database files, and chat histories remain strictly on the local operating system.

It consists of:
1. **Backend** (`backend/`): Python FastAPI server with 15 AI workers, orchestrator, and storage engine.
2. **App** (`app/`): Electron + React 19 desktop client with inline tool panels and live office visualization.

### Core Concepts
- **15 AI Workers:** Specialized roles across 4 departments (Leadership, Product, Engineering, Platform).
- **Hermes:** The Dispatcher Worker responsible for orchestrating tasks and managing the execution lifecycle.
- **Auto-Adaptive Context:** Dynamically adjusts context windows per model tier (thinker/crafter/sprinter).
- **Real Tool Execution:** Workers can read/write files, run shell commands, and search codebases.
- **Pipeline Orchestration:** Discovery → Planning → TaskGraph → Dispatch chain.
- **Permission System:** Per-worker tool restrictions enforced internally.

---

## Folder Structure

```
AI-Company/
├── app/                  # Electron + React desktop client
│   ├── src/
│   │   ├── main/         # Electron main process
│   │   ├── renderer/     # React frontend
│   │   └── preload/      # Electron preload scripts
│   ├── package.json
│   └── packaging/        # Python runtimes for bundling
├── backend/              # Python FastAPI backend
│   ├── backend/          # API routes, services, models
│   ├── agents/           # 15 AI worker definitions
│   ├── workers/          # Worker implementations
│   ├── llm/              # LLM provider abstraction
│   ├── storage/          # SQLite models and session
│   └── requirements.txt
├── docs/                 # Documentation and SoT
├── scripts/              # Build and utility scripts
├── .gitignore
└── README.md
```

---

## Development

### Prerequisites
- Node.js 20+
- Python 3.12+
- Wine (for Windows cross-compilation on Linux)

### Quick Start
```bash
# Install app dependencies
cd app && npm install

# Start dev server
npm run dev

# Build for production
npm run build:linux    # AppImage + deb
npm run build:win      # NSIS installer + portable
```

### Build Outputs
| Platform | File | Size |
|----------|------|------|
| Linux AppImage | `AIC-ADE-2.4.0-linux-x86_64.AppImage` | ~168MB |
| Linux deb | `AIC-ADE-2.4.0-linux-amd64.deb` | ~119MB |
| Windows Setup | `AIC-ADE-Setup-2.4.0.exe` | ~127MB |
| Windows Portable | `AIC-ADE-2.4.0-Windows-Portable.exe` | ~127MB |

---

## License

Proprietary — TVD
