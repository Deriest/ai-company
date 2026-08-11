# 🚀 MANUAL GITHUB RELEASE UPLOAD - v2.6.3

**Date:** 2026-08-11  
**Status:** ⚠️ **REQUIRES MANUAL UPLOAD TO GITHUB**  
**Version:** v2.6.3  
**Build Status:** ✅ Complete locally  

---

## 📦 Build Artifacts Ready

Located at `/home/tvd/AI-Company/app/dist/`:

| File | Size | SHA256 Checksum |
|------|------|-----------------|
| `aic-ade-2.6.3.AppImage` | 193 MB | `000745f772b53532ed83b0cdea277935be179b44a191ac776ce8827197e637e4` |
| `aic-ade_2.6.3_amd64.deb` | 138 MB | `c29bcfd7f1977ce7da9287413228095fdccacef7f6631b7aed8b76b03b2ad5bf` |
| `aic-ade Setup 2.6.3.exe` | 153 MB | `f1bfb2042863af5a27febf2eee2bbebcea6b9bf5e46b44fd3dac887e69d88c06` |

✅ All three files built successfully and verified

---

## 🔒 Security Fixes Included in v2.6.3

### Critical (4 items)
• Ed25519 signature verification for update manifests
• Enhanced JWT secret deployment instructions
• AIC_TESTING check moved before DB initialization
• SHA256 hash consistency fixes

### High Priority (5 items)
• Strengthened CSP headers with X-XSS-Protection
• Reduced port cache TTL (10s → 3s)
• Symlink TOCTOU vulnerability fix
• Backup lock race condition resolution
• SQLite WAL mode (already enabled)

### Medium Priority (5 items)
• IPC listener memory leak cleanup
• SSE buffer hardening (100KB/500KB limits)
• File operation error exposure to users
• Provider API key fail-fast validation
• Version comparison edge cases

### Low Priority (Selected)
• Deprecated pattern annotations added
• TypeScript strict mode already enabled (no action needed)

Full audit report available in repository documentation.

---

## 🏷️ Git State (Local)

**Commit:** `f686340`  
**Branch:** `main`  
**Tag:** v2.6.3 (not yet pushed)

```bash
git log --oneline -3
f686340 release: v2.6.3 — security fixes + build artifacts
5738cb3 release: v2.6.2 Production Hardening Release - All Issues Resolved
baa2ddc release: v2.6.1 Production Hardening Release
```

**Latest manifest:** `latest.json` created in repository root ✅

---

## 🔐 Authentication Issue

**Problem:** GitHub token needs refresh or manual upload required

The `release.sh` script completed builds but encountered authentication errors during GitHub release creation/upload phase. Local build is complete and artifacts are ready.

**Solution:** Manual upload via GitHub Web UI (same as v2.6.2)

---

## 📋 STEP-BY-STEP MANUAL UPLOAD INSTRUCTIONS

### Step 1: Create GitHub Release

1. Go to: https://github.com/Deriest/ai-company/releases/new
2. **Tag name**: `v2.6.3`
3. **Target**: Select `main` branch
4. **Release title**: `AIC-ADE v2.6.3 — Security Hardening Update`
5. **Description**:

```markdown
## v2.6.3 — Security Hardening Update

### 🔒 Critical Security Fixes (4 items)
• Ed25519 signature verification for updates (MITM protection)
• Enhanced JWT secret deployment instructions with production checklist
• AIC_TESTING check moved BEFORE database initialization
• SHA256 hash consistency in update validation

### 🛡️ High Priority Fixes (5 items)
• Strengthened CSP headers (X-XSS-Protection, frame-ancestors, upgrade-insecure-requests)
• Reduced port cache TTL from 10s → 3s for faster backend restart detection
• Symlink TOCTOU vulnerability fixed via file descriptor locking
• Backup lock race condition resolved with proper promise handling

### 📈 Medium Priority Fixes (5 items)
• IPC listener memory leak cleanup in preload.ts
• SSE buffer hardening with 100KB chunk / 500KB cumulative limits
• File operation errors now exposed to users via IPC
• Provider API key fail-fast validation on startup
• Version comparison edge cases handled correctly

### 🎯 Low Priority Improvements
• Deprecated pattern annotations added to codebase
• TypeScript strict mode already enabled (no action needed)

**Security Audit**: Comprehensive review completed, all critical/high issues resolved

SHA256 Checksums:
• AppImage: `000745f772b53532ed83b0cdea277935...`
• deb: `c29bcfd7f1977ce7da9287413228095f...`
• exe: `f1bfb2042863af5a27febf2eee2bbebc...`
```

6. Click **Create Release**

### Step 2: Upload Artifacts

Download the following files from local machine and upload to the newly created release page:

1. **aic-ade-2.6.3.AppImage** (193 MB)
   ```bash
   # Located at: /home/tvd/AI-Company/app/dist/aic-ade-2.6.3.AppImage
   # Copy to Windows/Mac/Linux desktop first, then drag-drop to GitHub
   ```

2. **aic-ade_2.6.3_amd64.deb** (138 MB)
   ```bash
   # Located at: /home/tvd/AI-Company/app/dist/aic-ade_2.6.3_amd64.deb
   ```

3. **aic-ade Setup 2.6.3.exe** (153 MB)
   ```bash
   # Located at: /home/tvd/AI-Company/app/dist/aic-ade Setup 2.6.3.exe
   ```

Click each file to upload it as a release asset.

### Step 3: Verify Upload

After uploading, verify all 3 assets appear on the release page:
- [ ] aic-ade-2.6.3.AppImage
- [ ] aic-ade_2.6.3_amd64.deb
- [ ] aic-ade Setup 2.6.3.exe

### Step 4: Commit latest.json

Back in terminal, commit and push the latest.json manifest:

```bash
cd /home/tvd/AI-Company
git add latest.json
git commit -m "release: v2.6.3 — latest.json manifest"
```

Then you'll need a **VALID GITHUB TOKEN** to push. If your current token doesn't work:

1. Generate new Personal Access Token at: https://github.com/settings/tokens
2. Scopes needed: `repo` (full control of private repositories)
3. Set environment variable:
   ```bash
   export GH_TOKEN=new_token_here
   ```
4. Push:
   ```bash
   git push origin main
   ```

### Step 5: Test Auto-Update

Deployed clients will automatically detect v2.6.3 by checking:
- URL: https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json
- Version: `"2.6.3"`
- Platforms have correct download URLs & SHA256 checksums

---

## 🔑 Troubleshooting

### Token Authentication Fails

If `git push` fails with "Invalid username or token":

1. **Generate new PAT** at https://github.com/settings/tokens/actions
2. **Scopes needed**: `repo` (complete access)
3. **Paste new token**: `export GH_TOKEN="<REDACTED - PLACEHOLDER FOR YOUR ACTUAL PERSONAL ACCESS TOKEN>"`
4. **Retry**: `git push origin main`

### GitHub Release Page Shows Empty Assets

This means upload failed:
- Re-check that all 3 files uploaded successfully
- Refresh browser after uploads complete
- Wait 1-2 minutes for CDN propagation

### Auto-Update Not Working

Verify `latest.json` format is correct:
```bash
curl https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json | python3 -m json.tool
```

Should return valid JSON with:
- `version`: "2.6.3"
- `platforms.linux.downloadUrl` pointing to release asset
- `platforms.win32.downloadUrl` pointing to installer

---

## ✅ Success Criteria

After completing all steps, you should see:

1. ✅ GitHub release page with 3 assets uploaded
2. ✅ `latest.json` accessible at GitHub raw URL
3. ✅ SHA256 checksums match downloaded files
4. ✅ Clients can auto-update to v2.6.3

---

**Questions?** See previous release documentation in this same directory.

**Next action**: Open GitHub releases page and follow Step 1-5 above.