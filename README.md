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

### Security — `AIC_JWT_SECRET` (server / shared-host deploys only)

**Desktop users can skip this section entirely** — the app auto-generates a
per-install secret (see the note above) and binds the backend to `127.0.0.1`.

Set `AIC_JWT_SECRET` only when running in **server / shared-host mode**, where
remote JWT authentication matters. Generate a secret and set it before launch:

```bash
# Generate:
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

```bash
# Linux/Mac:
export AIC_JWT_SECRET=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
npm start
```

```powershell
# Windows PowerShell:
$env:AIC_JWT_SECRET = (node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
npm start
```

⚠️ **Server-deploy checklist:** use a secure random secret (never example values),
set it before launch, never commit it to version control, and prefer a secret
manager (vault, Kubernetes secrets, etc.).

### Release Artifacts

| Platform | Download | Size |
|----------|----------|------|
| Linux AppImage | [v2.6.19](https://github.com/Deriest/ai-company/releases/download/v2.6.19/AIC-ADE-2.6.19.AppImage) | 221 MB |
| Linux DEB | [v2.6.19](https://github.com/Deriest/ai-company/releases/download/v2.6.19/aic-ade_2.6.19_amd64.deb) | 149 MB |
| Windows NSIS | [v2.6.19](https://github.com/Deriest/ai-company/releases/download/v2.6.19/AIC-ADE.SETUP.V2.6.19.exe) | 183 MB |

> **Auto-update:** installed apps poll `latest.json` on `raw.githubusercontent.com` and prompt when newer than the running build.

### Documentation Links

- [Architecture](docs/ARCHITECTURE.md) - System design & components
- [Product](docs/PRODUCT.md) - Feature specifications
- [Development](docs/DEVELOPMENT.md) - Build & dev conventions
- [Deployment](docs/DEPLOYMENT.md) - Build & release guides
- [Testing](docs/TESTING.md) - QA & validation strategies
- [Security](docs/SECURITY.md) - Security hardening notes

### Current Status

✅ **v2.6.19 Released** — Command Center composer rebuilt as a single centered row (`Hermes · Context · THINKER/CRAFTER/SPRINTER/VISION · Fetch · Compact`). Each tier is a button that opens a per-tier provider+model menu; selected model shows with a 27-char cap (full name on hover). Includes the accumulated renderer-packaging, backend boot-chain, onboarding, flicker, and JWT-optional local-first fixes from v2.6.13–2.6.18. A healthy packaged backend is verified via `GET /health 200` and automatic updates are served through `latest.json`.
⚪ **Next** — engine cold-start polish (10s boot timeout vs ~2s actual) and installer icon/site asset polish.
⚪ **Backlog** — multi-user scope TBD (local-first single-user is the product stance).

---

For detailed information, see individual documentation files or `docs/archive/` for historical reports.
