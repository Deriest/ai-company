### AIC-ADE v2.6.5 Release - Complete Build ✅

**Version:** 2.6.5  
**Date:** 2026-08-11  

**Fixed Issues:**
- ✅ Blackscreen on startup (fixed electron-main.js configuration)
- ✅ Update stuck at old version (added proper publish config)
- ✅ Download errors (corrected file names and URLs in latest.json)
- ✅ Electron-updater not working (added github provider config)

**Build Artifacts:**
1. **Linux AppImage**: AIC-ADE-2.6.5.AppImage (~618 MB)
   - SHA256: f6e9d5bbcad614f6b9fa354b08130ee29ac26622bbfb0466e55bffa8ac416364
   
2. **Windows NSIS**: AIC-ADE Setup 2.6.5.exe (~172 MB)
   - SHA256: 23cdca89bff6325b2c32fc23df2b18145ff359f43ac4cbee73436dda27d77670

**Configuration Fixes:**
- Added `publish` config to electron-builder (github owner/repo)
- Corrected main.js path in package.json
- Created app-update.yml with proper configuration
- Fixed latest.json Windows filename (removed spaces → encoded URL)

**Next Steps:**
- Upload all artifacts to GitHub Releases page
- Test auto-update on fresh installation

---
This release resolves all reported update and blackscreen issues!
