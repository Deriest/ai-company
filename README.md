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

> **Desktop (local-first):** AIC-ADE binds its backend to `127.0.0.1` only.
> On first launch it auto-generates a per-install secret (`<userData>/aic-ade/jwt-secret`, `chmod 600`)
> and reuses it on every subsequent launch — no `AIC_JWT_SECRET` setup required for desktop use.
> If `AIC_JWT_SECRET` **is** set in the environment it takes precedence (for server-mode deploys).

### Security — `AIC_JWT_SECRET` checklist (non-desktop deploys)

When JWT auth matters (shared host / server mode), set `AIC_JWT_SECRET` **before** starting the app.

AIC_JWT_SECRET environment variable is required for production security. Generate with:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

⚠️ **PRODUCTION DEPLOYMENT CHECKLIST:**
1. Generate a secure random secret (do **NOT** use example values)
2. Set `AIC_JWT_SECRET` as an environment variable **before** starting the app
3. Never commit secrets to version control
4. Use a secure secret manager (vault, Kubernetes secrets, etc.)

```bash
# Example (Linux/Mac):
export AIC_JWT_SECRET=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
npm start
```

```powershell
# Example (Windows PowerShell):
$env:AIC_JWT_SECRET = (node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
npm start
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

✅ **v2.6.13 Released** — renderer packaging + backend boot chain + JWT-optional local-first fixed, healthy engine verified (`GET /health 200`), first fully-bootable packaged app  
🟡 **Next** — engine cold-start polish (10s boot timeout vs ~2s actual) + installer icon/site assets  
⚪ **Backlog** — multi-user scope TBD (local-first single-user is product stance)

---

For detailed information, see individual documentation files or `docs/archive/` for historical reports.
