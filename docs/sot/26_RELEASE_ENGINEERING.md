# 26 — Release Engineering

**Subsystem:** Build, Packaging & Distribution Pipeline  

---

## 1. Release Generation Pipeline

1. **Version Bump:** Update `version` in `aic-ide/package.json` and NSIS installer `packaging/windows/aic-ade-setup.nsi`.
2. **Frontend & Main Compilation:** Run `npm run build` (tsc + vite build).
3. **Linux Distribution:** Run `npm run dist:linux` to produce AppImage and DEB packages.
4. **Windows Portable:** Run `npx electron-builder --win portable`.
5. **Windows Installer:** Run `makensis packaging/windows/aic-ade-setup.nsi` to compile setup executable.
6. **Checksum Generation:** Compute SHA256 hashes for all 4 artifacts and write `SHA256SUMS.txt`.
7. **Manifest Update:** Generate `latest.json` pointing to new version and hashes.
8. **LAN Server Sync:** Copy binaries, `latest.json`, and `SHA256SUMS.txt` to local update directory (`releases/AIC-ADE/`).
