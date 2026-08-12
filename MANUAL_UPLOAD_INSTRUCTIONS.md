# 📤 MANUAL UPLOAD INSTRUCTIONS - AIC-ADE v2.6.10

## GitHub Release Upload Required

API upload failed (HTTP 422 error). Please upload manually via web interface.

---

## Step-by-Step Manual Upload

### 1. Go to GitHub Releases
```
https://github.com/Deriest/ai-company/releases/tag/v2.6.10
```

### 2. Click "Edit" on existing release

### 3. Drag & Drop These Files From:
```
/home/tvd/AI-Company/app/dist/
```

**Files to Upload:**

| File | Size | Purpose |
|------|------|---------|
| **AIC-ADE Setup 2.6.10.exe** | 145.0 MB | Windows NSIS installer |
| **AIC-ADE-2.6.10.AppImage** | 176.6 MB | Linux AppImage |
| **aic-ade_2.6.10_amd64.deb** | 129.3 MB | Linux .deb package |

### 4. Verify All Files Uploaded

After uploading, you should see all 3 files listed under "Assets" section of the release.

### 5. Publish Changes

Click "Save changes" or "Update release" to make the new binaries available.

---

## Verification Commands (After Upload)

```bash
# Check that assets are visible
curl -sL "https://api.github.com/repos/Deriest/ai-company/releases/tags/v2.6.10" \
  -H "Authorization: token YOUR_TOKEN" | jq '.assets[].name'

# Should show:
# "AIC-ADE Setup 2.6.10.exe"
# "AIC-ADE-2.6.10.AppImage"  
# "aic-ade_2.6.10_amd64.deb"
```

---

## Why Manual Upload Needed?

GitHub API has limitations:
- Large file uploads (>100MB) can timeout
- Rate limits may block multiple simultaneous uploads
- Some authentication configurations don't support asset uploads via API

Web UI is more reliable for large files! ✅

---

## Final Verification Checklist

- [ ] Release v2.6.10 exists with correct title
- [ ] All 3 binary files uploaded and visible
- [ ] File sizes match above (within ~5%)
- [ ] Release notes updated with fix description
- [ ] Users can download from release page

---

**Upload Date:** 2026-08-12  
**Fix Status:** READY FOR PRODUCTION ✨
