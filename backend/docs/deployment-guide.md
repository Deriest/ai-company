# AIC Platform - Deployment Guide

**Version:** 1.0.0  
**Date:** 2026-07-21  
**Status:** Production Ready

---

## Quick Start (Docker)

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 10GB disk space

### 1. Clone & Configure

```bash
git clone <repository>
cd aic-platform

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Build & Run

```bash
# Build frontend first
cd frontend && npm install && npm run build && cd ..

# Start with Docker Compose
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f backend
```

### 3. Access

- **Application:** http://localhost:8000
- **Health Check:** http://localhost:8000/api/health
- **Default Login:** admin / admin123

---

## Manual Deployment

### System Requirements

- **OS:** Ubuntu 20.04+ / Debian 11+
- **Python:** 3.12+
- **Node.js:** 20+
- **RAM:** 2GB minimum, 4GB recommended
- **CPU:** 2 cores minimum
- **Disk:** 10GB minimum

### 1. Install Dependencies

```bash
# System packages
sudo apt update
sudo apt install -y python3.12 python3.12-venv nodejs npm

# Python environment
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
npm run build
cd ..
```

### 2. Configure Environment

```bash
# Create .env file
cp .env.example .env

# Generate JWT secret
openssl rand -hex 32

# Edit .env with your configuration
nano .env
```

### 3. Initialize Database

```bash
source venv/bin/activate

# Database will auto-initialize on first run
# Create default admin user
python3 -c "
from storage.database import init_db
import asyncio
asyncio.run(init_db())
"
```

### 4. Run Application

```bash
# Development
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Production (with systemd)
sudo cp deployment/aic-platform.service /etc/systemd/system/
sudo systemctl enable aic-platform
sudo systemctl start aic-platform
sudo systemctl status aic-platform
```

---

## Production Deployment

### Using Systemd

Create `/etc/systemd/system/aic-platform.service`:

```ini
[Unit]
Description=AIC Platform
After=network.target

[Service]
Type=simple
User=aic
Group=aic
WorkingDirectory=/opt/aic-platform
Environment="PATH=/opt/aic-platform/venv/bin"
ExecStart=/opt/aic-platform/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Using Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

### SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Configuration Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | JWT signing key | - | Yes |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./data/aic.db` | No |
| `LLM_PROVIDER_URL` | LLM provider endpoint | - | Yes |
| `LLM_API_KEY` | LLM API key | - | Yes |
| `CORS_ORIGINS` | Allowed CORS origins | `*` | No |
| `HOST` | Server bind address | `0.0.0.0` | No |
| `PORT` | Server port | `8000` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `PRODUCTION` | Production mode | `false` | No |

### Database

**SQLite (Default)**
```
DATABASE_URL=sqlite+aiosqlite:///./data/aic.db
```

**PostgreSQL (Recommended for Production)**
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/aic
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Application health
curl http://localhost:8000/api/health

# Expected response:
{
  "status": "healthy",
  "service": "aic-platform",
  "database": "connected"
}
```

### Logs

```bash
# Docker Compose
docker-compose logs -f backend

# Systemd
sudo journalctl -u aic-platform -f

# Application logs
tail -f logs/aic-platform.log
```

### Database Backup

```bash
# SQLite
cp data/aic.db data/aic.db.backup.$(date +%Y%m%d)

# Automated backup (cron)
0 2 * * * /opt/aic-platform/scripts/backup.sh
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild frontend
cd frontend && npm run build && cd ..

# Restart service
docker-compose restart backend
# or
sudo systemctl restart aic-platform
```

---

## Troubleshooting

### Application won't start

```bash
# Check logs
docker-compose logs backend

# Check environment
cat .env

# Verify database
ls -lh data/aic.db

# Test database connection
python3 -c "import sqlite3; sqlite3.connect('data/aic.db').execute('SELECT 1')"
```

### Frontend not loading

```bash
# Verify build
ls -lh frontend/dist/

# Rebuild frontend
cd frontend && npm run build && cd ..

# Clear browser cache
```

### LLM provider errors

```bash
# Test provider connection
curl -X POST http://172.19.0.2:20128/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"FREE","messages":[{"role":"user","content":"test"}]}'

# Check provider configuration
curl http://localhost:8000/api/llm/providers
```

### Database locked errors

```bash
# Check WAL mode
sqlite3 data/aic.db "PRAGMA journal_mode;"

# Should return: wal

# If not, set it:
sqlite3 data/aic.db "PRAGMA journal_mode=WAL;"
```

---

## Performance Tuning

### Uvicorn Workers

```bash
# Multiple workers (production)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# Single worker (development)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Database Optimization

```sql
-- SQLite optimizations
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;
PRAGMA busy_timeout=30000;
```

### Nginx Caching

```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## Security Checklist

- [ ] Change default admin password
- [ ] Generate strong JWT secret
- [ ] Configure CORS origins
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Set up firewall rules
- [ ] Regular database backups
- [ ] Monitor logs for suspicious activity
- [ ] Keep dependencies updated
- [ ] Rate limiting configured
- [ ] Disable debug mode in production

---

## Scaling

### Horizontal Scaling

1. Use PostgreSQL instead of SQLite
2. Add load balancer (nginx/HAProxy)
3. Multiple backend instances
4. Shared session storage (Redis)

### Vertical Scaling

- Increase worker count
- Optimize database queries
- Add caching layer
- Use CDN for static assets

---

## Support

For issues and questions:
- Check logs first
- Review documentation
- Check GitHub issues
- Contact support team

---

**Last Updated:** 2026-07-21  
**Version:** 1.0.0
