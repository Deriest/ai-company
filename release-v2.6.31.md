# AIC-ADE v2.6.31 Release Checklist

## Version Information
- **Version**: 2.6.31
- **Git Commit**: `9e87e5b`
- **Release Date**: 2026-08-18

## What's New
✨ **Auto-generate JWT secret for production security**
- Backend now automatically generates a secure 256-bit random hex JWT secret on first startup
- No manual setup required - just start the app!
- Same secret persists across restarts (stored in `.jwt_secret`)
- Git-safe storage with restricted permissions (0600)
- Optional `AIC_JWT_SECRET` environment variable override still supported

## Files Updated
- ✅ `package.json` - Root version bumped to 2.6.31
- ✅ `app/package.json` - App version and metadata bumped to 2.6.31
- ✅ `latest.json` - Manifest updated with new version and release notes
- ✅ `README.md` - Changelog updated for v2.6.31
- ✅ `backend/backend/config.py` - Auto-generation logic implemented
- ✅ `backend/tests/test_jwt_secret_enforcement.py` - Tests updated

## Build Instructions

### Step 1: Clean old artifacts
```bash
cd /home/tvd/AI-Company/app
rm -rf release/
```

### Step 2: Build Windows installer
```bash
npm run dist:win
```
Expected output: `AIC-ADE-Setup-2.6.31.exe` (~143 MB)

### Step 3: Build Linux packages
```bash
npm run dist:linux
```
Expected outputs:
- `AIC-ADE-2.6.31-linux-x86_64.AppImage` (~188 MB)
- `AIC-ADE-2.6.31-linux-amd64.deb` (~126 MB)

### Step 4: Calculate SHA256 checksums
```bash
cd app/release
sha256sum *.{exe,AppImage,deb} > SHA256SUMS.new
cat SHA256SUMS.new
```

### Step 5: Update latest.json with real hashes
```bash
node scripts/update_manifest.js 2.6.31
```

### Step 6: Sign the manifest
```bash
node scripts/sign_manifest.js latest.json secrets/release_private_key.pem
```

### Step 7: Verify signature
```bash
node test_verify.js  # Should show "SIGNATURE VERIFIED"
```

### Step 8: Commit release changes
```bash
cd /home/tvd/AI-Company
git add app/release/ README.md package.json app/package.json latest.json
git commit -m "release: v2.6.31 — Auto-generate JWT secret"
git push origin main
```

### Step 9: Create GitHub Release
1. Go to https://github.com/Deriest/ai-company/releases/new
2. Tag: `v2.6.31`
3. Target: Current HEAD (`9e87e5b`)
4. Title: "AIC-ADE v2.6.31"
5. Release notes: Copy from README.md changelog section
6. Upload assets:
   - `AIC-ADE-Setup-2.6.31.exe`
   - `AIC-ADE-2.6.31-linux-x86_64.AppImage`
   - `AIC-ADE-2.6.31-linux-amd64.deb`
   - `latest.json` (copy from root)
   - `latest.json.sig` (copy from app/release/)

### Step 10: Verify public access
```bash
curl -sL https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json | jq .version
# Should return: "2.6.31"
```

## Verification Steps
- [ ] Windows exe downloadable via GitHub releases
- [ ] Linux AppImage downloadable via GitHub releases  
- [ ] Linux deb downloadable via GitHub releases
- [ ] `latest.json` accessible at raw.githubusercontent.com
- [ ] Ed25519 signature verification passes locally
- [ ] SHA256 hashes match between files and manifest
- [ ] Auto-update check simulation works

## Rollback Plan
If issues discovered:
1. Do NOT delete old releases (keep them available)
2. Tag new version anyway as `v2.6.31-rolling-backout`
3. User can manually download previous working version

## Notes
- First release with auto-JWT-secret feature
- All existing functionality preserved
- Zero configuration required for users
- Backward compatible (users who already have `AIC_JWT_SECRET` env var will continue to use it)
