# AIC-ADE Deployment Guide

## Overview

AIC-ADE is a desktop application that runs locally on your machine. This guide covers building and distributing the application.

## Prerequisites

### Development
- Node.js 18+ and npm
- Python 3.11+
- Git

### Building
- All development prerequisites
- Platform-specific tools:
  - **Windows**: Visual Studio Build Tools
  - **macOS**: Xcode Command Line Tools
  - **Linux**: build-essential, rpm, dpkg

## Local Development Setup

### Backend Setup
```bash
# Clone repository
git clone https://github.com/your-org/aic-platform.git
cd aic-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r backend/requirements.txt

# Start backend
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Setup
```bash
# Navigate to frontend
cd ../aic-ide

# Install dependencies
npm install

# Start development server
npm run dev
```

### Electron Development
```bash
# Build and run Electron app
npm run dev
```

## Production Build

### Build Commands
```bash
# Build for current platform
npm run build

# Build for specific platforms
npm run build:linux    # AppImage + deb
npm run build:win      # Portable exe
npm run build:mac      # DMG
```

### Build Output
- **Linux**: `dist/AIC-ADE-*.AppImage`, `dist/aic-ade_*.deb`
- **Windows**: `dist/AIC-ADE-*.exe`
- **macOS**: `dist/AIC-ADE-*.dmg`

## Environment Variables

### Backend
| Variable | Description | Default |
|----------|-------------|---------|
| `AIC_DATA_DIR` | Data storage directory | `/tmp/aic-data` |
| `AIC_LLM_BASE_URL` | LLM provider URL | None |
| `AIC_LLM_API_KEY` | LLM provider API key | None |

### Frontend
| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `http://127.0.0.1:8000` |

## Database

### Location
Default: `/tmp/aic-data/aic.db`

### Migrations
Migrations run automatically on startup.

### Backup
```bash
# Backup database
cp /tmp/aic-data/aic.db /path/to/backup/aic.db
```

### Restore
```bash
# Restore database
cp /path/to/backup/aic.db /tmp/aic-data/aic.db
```

## Configuration

### Backend Configuration
Configuration is done via environment variables or `.env` file.

### Frontend Configuration
Configuration is done via environment variables or `src/renderer/src/lib/api/client.ts`.

## Security Considerations

### Localhost-Only
- Backend binds to `127.0.0.1` only
- No external network exposure
- CORS restricted to localhost

### Data Privacy
- All data stored locally
- No telemetry or analytics
- No cloud synchronization

### API Keys
- Stored encrypted in database
- Never transmitted to third parties
- User manages their own keys

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows
```

### Database Locked
```bash
# Remove lock file
rm /tmp/aic-data/aic.db-lock
```

### Build Failures
```bash
# Clean and rebuild
rm -rf node_modules dist
npm install
npm run build
```

## Distribution

### Linux
- AppImage: Universal, no installation required
- deb: Debian/Ubuntu package manager
- rpm: Red Hat/Fedora package manager

### Windows
- Portable: Single exe, no installation
- Installer: Standard Windows installer

### macOS
- DMG: Standard macOS disk image

## Updates

### Auto-Updates
AIC-ADE supports auto-updates via GitHub releases.

### Manual Updates
1. Download latest release
2. Install over existing installation
3. Data is preserved automatically

## Support

- **Documentation**: `docs/` directory
- **Issues**: GitHub Issues
- **Community**: Discord
