# AIC Platform — Deployment Guide

## Prerequisites

- Docker 20+ and Docker Compose v2
- OR Python 3.11+ and Node.js 20+

## Quick Start (Docker)

```bash
cd deployment
cp .env.example .env
# Edit .env — change SECRET_KEY!
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/health

## Development Setup

### Backend

```bash
cd aic-platform
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd aic-platform/frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 with API proxy to :8000.

## Default User

Register via API or UI:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password","role":"owner"}'
```

## Data Persistence

- SQLite database: `data/aic.db`
- Task artifacts: `data/tasks/`
- Docker volume: `./data:/app/data`

## Backup

```bash
# Stop services
docker compose down

# Backup data
tar -czf aic-backup-$(date +%Y%m%d).tar.gz data/

# Restore
tar -xzf aic-backup-YYYYMMDD.tar.gz
docker compose up -d
```

## PostgreSQL Migration

1. Change `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aic
   ```
2. Install asyncpg: `pip install asyncpg`
3. Run migrations (tables auto-create on startup)

## Health Checks

- Backend: `GET /health` → `{"status":"ok"}`
- Docker: built-in healthcheck every 30s
- Frontend: served by nginx, proxied health check

## Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Nginx (Docker) / Vite (dev) |
| Backend | 8000 | FastAPI + Uvicorn |
| WebSocket | 8000 | /ws/{channel} |

## Cross-Platform Support

### Linux
- Native: Python 3.11+ + Node.js 20+
- Docker: `docker compose up`

### Windows
- Docker Desktop: `docker compose up`
- Native: WSL2 + Python + Node.js

### macOS
- Docker Desktop: `docker compose up`
- Native: Homebrew Python + Node.js

## Troubleshooting

### Port already in use
```bash
# Change port in .env
PORT=8001
```

### Database locked
```bash
# Stop all services, then restart
docker compose down
docker compose up -d
```

### Frontend can't reach API
- Check backend is running: `curl http://localhost:8000/health`
- Check CORS_ORIGINS in `.env` includes your frontend URL
