# 🎉 AIC-ADE v2.6.9 - RELEASE COMPLETE

**Release Date:** 2026-08-12  
**Version:** 2.6.9  
**Status:** ✅ Code pushed, ⚠️ Assets need manual upload  

---

## 🐛 What Was Fixed

### Critical Bug Fix
- ✅ **Blank Screen Issue Resolved**
  - Chat view was showing black screen when clicking "Chat" menu
  - Root cause: Dead code `return null;` in switch statement left over from refactoring
  - Solution: Removed redundant cases for "hermes" and "chat" views
  - File affected: `app/src/renderer/src/App.tsx` (lines 182-184)

---

## 📦 Generated Artifacts

All binaries built successfully and stored in `app/dist/`:

| File | Platform | Size | Type |
|------|----------|------|------|
| `AIC-ADE Setup 2.6.9.exe` | Windows x64 | 132.85 MB | NSIS Installer |
| `AIC-ADE-2.6.9.AppImage` | Linux portable | 164.86 MB | Self-executable |
| `aic-ade_2.6.9_amd64.deb` | Linux Debian | 119.77 MB | Package Manager |

---

## 🔧 Auto-update Configuration

**Unified latest.json** created with single file for ALL platforms:

```json
{
  "version": "2.6.9",
  "channel": "stable",
  "releaseDate": "2026-08-12",
  "platforms": {
    "win32": { ... },      // Windows NSIS installer
    "linux": { ... },      // AppImage
    "linux-deb": { ... }   // .deb package
  }
}
```

🌐 **Live at:** https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json

---

## 🚀 NEXT STEPS - UPLOAD ASSETS MANUALLY

⚠️ **IMPORTANT:** GitHub release created, but assets need manual upload due to API limitations.

### Step 1: Go to Release Page
Visit: https://github.com/Deriest/ai-company/releases/tag/v2.6.9

### Step 2: Upload Files
Drag and drop these 3 files from your local machine:

```bash
/home/tvd/AI-Company/app/dist/
├── AIC-ADE Setup 2.6.9.exe           (132.85 MB)
├── AIC-ADE-2.6.9.AppImage            (164.86 MB)
└── aic-ade_2.6.9_amd64.deb           (119.77 MB)
```

### Step 3: Verify SHA256 Checksums

Optional verification - check file integrity:

```bash
cd /home/tvd/AI-Company/app/dist

sha256sum AIC-ADE\ Setup\ 2.6.9.exe
sha256sum AIC-ADE-2.6.9.AppImage
sha256sum aic-ade_2.6.9_amd64.deb

# Should match SHA256 in latest.json:
# • exe: 463d3c51cc459e0c95b9f1461c897c9af709448c48c4f9dc780b91856836edea
# • appimage: 064d2fd634d7aec23b6c1b81cef835231ef079ce96bb6f15553e4c48f10a1d2e
# • deb: 1ffbc532e44e43344531834b66c648d2066ac9a9d052482a74a5b88f528dc448
```

### Step 4: Share Release
Once uploaded:
- Notify users about the bug fix
- Share download links
- Test installation on fresh system

---

## ✅ What's Already Done

- ✅ Version bumped to v2.6.9 in `package.json`
- ✅ Blank screen bug fixed in `App.tsx`
- ✅ All 3 platform binaries built successfully
- ✅ SHA256 checksums computed
- ✅ Unified `latest.json` created (single manifest for all platforms)
- ✅ Git commit created with detailed message
- ✅ Pushed to GitHub main branch
- ✅ GitHub Release v2.6.9 tag created

---

## 🔍 Technical Details

### Build Commands Used
```bash
npm run build                     # TypeScript + Vite frontend
npm run dist:win                  # Windows NSIS installer
npm run dist:linux                # Linux AppImage + deb
```

### Environment
- Node.js: v20.20.2
- npm: v10.8.2
- electron-builder: v25.1.8
- Electron: v34.5.8

### Git Commit
```
commit 3aa4a3c
Author: tvd
Date: 2026-08-12

release: v2.6.9 — Blank screen fix, unified latest.json for all platforms

- Fixed blank screen issue by removing dead code in Chat view
- Built Windows NSIS installer (AIC-ADE Setup 2.6.9.exe)
- Built Linux AppImage (AIC-ADE-2.6.9.AppImage) + deb (aic-ade_2.6.9_amd64.deb)
- Created unified latest.json with SHA256 checksums for auto-update
```

---

## 🎯 Success Criteria Met

| Task | Status |
|------|--------|
| Fix blank screen bug | ✅ Complete |
| Build Windows installer | ✅ Complete |
| Build Linux packages | ✅ Complete |
| Generate latest.json | ✅ Complete |
| Create unified manifest | ✅ Complete |
| Compute SHA256 hashes | ✅ Complete |
| Commit changes | ✅ Complete |
| Push to GitHub | ✅ Complete |
| Create GitHub Release tag | ✅ Complete |
| Upload artifacts | ⏸️ Manual step required |

---

## 📞 Support

For questions or issues with this release:
1. Check release notes above
2. Review git commit for details
3. Contact developer directly

---

**Release Prepared:** 2026-08-12  
**Last Updated:** 2026-08-12 19:12 UTC
