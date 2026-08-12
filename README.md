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

| Platform | Download | Status |
|----------|----------|--------|
| Linux AppImage | [v2.6.6](https://github.com/Deriest/ai-company/releases/download/v2.6.6/AIC-ADE-2.6.6.AppImage) | ✅ |
| Linux DEB | [v2.6.6](https://github.com/Deriest/ai-company/releases/download/v2.6.6/aic-ade_2.6.6_amd64.deb) | ✅ |
| Windows NSIS | [v2.6.6](https://github.com/Deriest/ai-company/releases/download/v2.6.6/AIC-ADE.Setup.2.6.6.exe) | ✅ |

### Documentation Links

- [Architecture](docs/ARCHITECTURE.md) - System design & components
- [Product](docs/PRODUCT.md) - Feature specifications
- [Deployment](docs/DEPLOYMENT.md) - Build & release guides
- [Testing](docs/TESTING.md) - QA & validation strategies
- [Security](docs/SECURITY.md) - Security hardening notes

### Current Status

✅ **v2.6.6 Released** - Security hardening + Python runtime bundle  
🟡 **In Progress** - Agent performance optimization  
⚪ **Backlog** - Multi-user support investigation

---

For detailed information, see individual documentation files or `docs/archive/` for historical reports.
