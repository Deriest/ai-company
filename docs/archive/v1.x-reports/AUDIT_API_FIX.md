# Fix: API route not found /api/audit

## Root Cause
Frontend sudah diupdate ke `/dashboard/audit`, tapi browser masih load JS bundle lama yang manggil `/audit`.

## Verification
```bash
# OpenAPI endpoints available:
/api/dashboard/audit  ✓
/api/console/audit    ✓
/api/audit            ✗ (not registered)

# Frontend code:
./pages/Audit.tsx:44  → api.get('/dashboard/audit?limit=100')  ✓ CORRECT
```

## Solution
**Browser hard refresh diperlukan** karena:
1. Vite production build menghasilkan hashed filenames (`index-C72XeRCo.js`)
2. Browser mungkin masih cache versi lama (`index-Bifhut5M.js` atau sebelumnya)
3. Service worker atau HTTP cache bisa serve old bundle

## User Action Required
Buka http://192.168.2.10:8000 dan lakukan **hard refresh**:

**Chrome/Edge:** `Ctrl + Shift + R` atau `Ctrl + F5`  
**Firefox:** `Ctrl + Shift + R` atau `Ctrl + F5`  
**Safari:** `Cmd + Option + R`

Atau:
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

## Latest Build
```
dist/assets/index-C72XeRCo.js   325.00 kB │ gzip: 95.93 kB
dist/assets/index-BThYjJJ-.css   75.54 kB │ gzip: 14.59 kB
```

File hash `C72XeRCo` adalah versi terbaru dengan audit fix.

## If Error Persists After Hard Refresh
Check browser DevTools Network tab:
1. Look for request to `/api/audit`
2. Check which JS file initiated the request
3. Verify JS filename matches `index-C72XeRCo.js` (latest hash)

If old hash still loading, check:
- Service worker status (Application tab > Service Workers > Unregister)
- Server cache (restart backend if using in-memory cache)

---

**Status:** Frontend code correct, build updated, browser cache refresh needed  
**Time:** 2026-07-22 02:48
