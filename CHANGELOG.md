# Changelog

All notable changes to AIC-ADE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- IMPROVEMENT_LOG.md for tracking perpetual improvement loop cycles

---

## [2.6.34] - 2026-08-XX

### Changed
- Updated download links to latest stable release

### Download Links
- Windows x64: [`AIC-ADE-Setup-2.6.34.exe`](https://github.com/Deriest/ai-company/releases/download/v2.6.34/AIC-ADE-Setup-2.6.34.exe) (143.66 MB)
- Linux AppImage: [`AIC-ADE-2.6.34-linux-x86_64.AppImage`](https://github.com/Deriest/ai-company/releases/download/v2.6.34/AIC-ADE-2.6.34-linux-x86_64.AppImage) (188.12 MB)
- Linux Debian: [`AIC-ADE-2.6.34-linux-amd64.deb`](https://github.com/Deriest/ai-company/releases/download/v2.6.34/AIC-ADE-2.6.34-linux-amd64.deb) (125.84 MB)

---

## [2.6.30] - 2026-07-XX

### 🚨 Critical Security Fix — Ed25519 Signature Verification

**This release fixes a critical bug that prevented auto-update from working.**

#### What Was Fixed

- **Cryptographic implementation**: Rewrote `updateSecurity.ts` to use JWK format matching `sign_manifest.js`
  - Old: `createVerify("SHA256").verify()` with DER SPKI → threw `error:0680009B:asn1 encoding routines::too long`
  - New: Direct SHA256 digest + JWK key object → verified correctly ✅

- **Package contents**: Added `latest.json` and `latest.json.sig` to electron-builder files list
  - Both manifest and cryptographic signature now included in all installers
  - Users can verify update authenticity before downloading

- **Backend modules**: All 30+ Python modules (api, database, middleware, models, security, services) included in every build
  - Linux AppImage: 188.12 MB (fully functional backend)
  - Linux Debian: 125.84 MB (with system integration)
  - Windows NSIS: 143.66 MB (bundled Python runtime)

#### Impact

- **Before fix**: Install fails immediately on first launch; backend can't start; update checks fail with "MITM attack" error
- **After fix**: Full application operational; auto-update works securely with cryptographic verification; all features functional

#### Technical Details

```bash
# Verify signature independently
node -e 'const crypto=require("crypto"); const sig=require("latest.json.sig"); const data=require("latest.json"); const hash=crypto.createHash("sha256").update(JSON.stringify(data)).digest(); const valid=crypto.verify(null, hash, {...publicKey}, Buffer.from(sig,"base64")); console.log("Valid:",valid);'
```

---

## Historical Releases

For earlier releases and detailed release notes, see the [GitHub Releases page](https://github.com/Deriest/ai-company/releases).

---

## Notes

- All releases include automatic update verification via Ed25519 signatures
- SHA256 checksums published alongside each artifact
- Local-first architecture: no data leaves your machine
- BYOK (Bring Your Own Key): only user-configured providers used
