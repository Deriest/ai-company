# AI-Company (AIC-ADE)

## Overview

**AI-Company Advanced Development Environment (AIC-ADE)** is a desktop IDE for autonomous software engineering with multi-agent collaboration, real-time AI assistants, and integrated development workflows.

### Key Capabilities

- **Multi-Agent Orchestration**: Coordinate multiple specialized agents (Explorer, Fixer, Designer, Oracle, Librarian)
- **Real-Time Chat Interface**: Async chat with live streaming responses
- **Backend-Powered Services**: Python backend with FastAPI for agent execution
- **Electron Desktop App**: Cross-platform UI with native integrations
- **Self-Documenting Code**: Codemap generation, AGENTS.md instructions
- **Auto-Update System**: Latest.json manifest for version discovery

### Project Structure

```
AI-Company/
├── app/           # Electron frontend
├── backend/       # Python backend services  
├── docs/          # Documentation
│   ├── archive/   # Historical reports
│   └── [canonical docs]
├── scripts/       # Build/release automation
└── tests/         # Test suites
```

### Quick Start

```bash
# Install dependencies
cd app && npm install

# Start development
npm run dev

# Build for production
npm run build:electron
```

### Release Artifacts

| Platform | Download | Size |
|----------|----------|------|
| Linux AppImage | [v2.6.13](https://github.com/Deriest/ai-company/releases/download/v2.6.13/AIC-ADE-2.6.13.AppImage) | 221 MB |
| Linux DEB | [v2.6.13](https://github.com/Deriest/ai-company/releases/download/v2.6.13/aic-ade_2.6.13_amd64.deb) | 151 MB |
| Windows NSIS | [v2.6.13](https://github.com/Deriest/ai-company/releases/download/v2.6.13/AIC-ADE.SETUP.V2.6.13.exe) | 183 MB |

> **Auto-update:** installed apps poll `latest.json` on `raw.githubusercontent.com` and prompt when newer than the running build.

### Documentation Links

- [Architecture](docs/ARCHITECTURE.md) - System design & components
- [Product](docs/PRODUCT.md) - Feature specifications
- [Deployment](docs/DEPLOYMENT.md) - Build & release guides
- [Testing](docs/TESTING.md) - QA & validation strategies
- [Security](docs/SECURITY.md) - Security hardening notes

### Current Status

✅ **v2.6.13 Released** — renderer packaging + backend boot chain fixed, healthy engine verified (`GET /health 200`), first fully-bootable packaged app  
🟡 **Next** — engine cold-start polish (10s boot timeout vs ~2s actual) + installer icon/site assets  
⚪ **Backlog** — multi-user scope TBD (local-first single-user is product stance)

---

For detailed information, see individual documentation files or `docs/archive/` for historical reports.
