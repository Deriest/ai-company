# Deployment & Release Guide

## Build System

### Prerequisites
- Node.js 18+ 
- Python 3.10+
- Electron build tools

### Build Commands

```bash
# Frontend only
npm run build

# Electron TypeScript compilation
npm run build:electron

# Full production build (Linux + Windows)
bash scripts/release.sh {{VERSION}}  # contoh: 2.6.25
```

## Output Artifacts

### Linux
- `release/AIC-ADE-{{VERSION}}.AppImage` - Portable AppImage (~237MB)
- `release/aic-ade_{{VERSION}}_amd64.deb` - Debian package (~184MB)

### Windows  
- `release/AIC-ADE.SETUP.V{{VERSION}}.exe` - NSIS installer (~229MB)

### File Sizes (v2.6.25)
| Format | Size | Content |
|--------|------|---------|
| AppImage | 158 MB | Electron + Python runtime bundled |
| DEB | 115 MB | Standalone with system dependencies |
| EXE | 127 MB | Windows executable + resources |

## Auto-Update Configuration

### Manifest URL
```
https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json
```

### latest.json Structure
```json
{
  "version": "2.6.25",
  "platforms": {
    "linux": { "filename": "AIC-ADE-2.6.25.AppImage", ... },
    "win32": { "filename": "AIC-ADE.SETUP.V2.6.25.exe", ... }
  }
}
```

### Update Flow
1. App starts → checks manifest URL
2. Compares version numbers
3. If newer version found → downloads assets
4. Verifies SHA256 checksums
5. Installs update on next restart

## Release Process

### 1. Bump Version
```bash
# app/package.json
"version": "2.6.25"

# backend/backend/__init__.py
__version__ = "{{NEW_VERSION}}"
```

### 2. Build & Test
```bash
bash scripts/release.sh {{NEW_VERSION}}
pytest tests/integration/ -xvs
```

### 3. Upload to GitHub
- Create release tag on GitHub
- Upload binaries to release assets
- Update latest.json with correct URLs and checksums

### 4. Push to Main
```bash
git add latest.json
git commit -m "release: v{{NEW_VERSION}}"
git push origin main
```

### 5. Verify Auto-Update
- Install versi lama
- Run app and trigger update check
- Confirm update ke {{NEW_VERSION}} mulai terunduh otomatis

## CI/CD Integration

### Recommended Pipeline
```yaml
stages:
  - test: pytest tests/
  - build: npm run build && bash scripts/release.sh $VERSION
  - upload: github releases API
  - verify: test auto-update endpoint
```

### Environment Variables
```bash
GITHUB_TOKEN: Personal access token for API uploads
APPVEYOR_TOKEN: For Appveyor (if used)
```

## Rollback Strategy

If update fails:
1. Keep previous version available in releases
2. Update latest.json to point to previous version
3. Document issue in CHANGELOG.md

## Troubleshooting

### Build Failures
- Check Node.js version compatibility
- Verify Python dependencies installed
- Clean build artifacts before retry: `rm -rf dist/`

### Update Check Fails
- Verify latest.json is publicly accessible
- Check SHA256 checksums are accurate
- Ensure GitHub release exists with matching tag

## Deployment Checklist

- [ ] All tests passing
- [ ] SHA256 checksums verified
- [ ] Binary signatures applied (if enterprise)
- [ ] latest.json updated with correct values
- [ ] Release notes written
- [ ] Changelog updated
- [ ] Git tag created
- [ ] Assets uploaded to GitHub
- [ ] Auto-update tested on fresh install
