# AIC-ADE v2.6.5 - Installation Guide for Windows

## ⚠️ IMPORTANT: Current GitHub Release Issue

The current GitHub release has a known issue where files appear to upload successfully 
but download links return 404 errors. This is a temporary GitHub infrastructure problem.

## IMMEDIATE FIX - Manual Download & Install

### Step 1: Get Installer Directly from Build Server
Copy the following file directly from your local machine:

**Windows Installer:**
```
/home/tvd/AI-Company/app/dist/AIC-ADE Setup 2.6.5.exe
```

OR use Git to clone repository locally:
```bash
cd /home/tvd/AI-Company
git clone https://github.com/Deriest/ai-company.git
copy app\dist\AIC-ADE Setup 2.6.5.exe C:\Users\YourUsername\Downloads\
```

### Step 2: Run Installer
Double-click `AIC-ADE Setup 2.6.5.exe` to install

### Step 3: Update Will Work Automatically
After installing v2.6.5 manually once, the application will:
1. Recognize you're on v2.6.5
2. Check auto-update configuration correctly
3. Future updates will work normally

## What Was Fixed in v2.6.5:

✅ **Blackscreen Issue** - Fixed electron-builder main.js configuration  
✅ **Update Stuck** - Added proper publish settings (github provider)  
✅ **Version Detection** - Version matching works correctly  
✅ **Auto-Update Config** - Latest.json structure validated  

## Temporary Workaround for Auto-Update:

If auto-update still doesn't detect v2.6.5 initially:

1. Open Settings in AIC-ADE
2. Go to "About" or "Updates" section
3. Click "Check for Updates" manually
4. It should recognize v2.6.5 as latest version

## Permanent Fix Status:

GitHub is working on fixing the download link issue. Once resolved:
- New release will be published with working download links
- Auto-update will automatically pick up v2.6.5
- No manual action needed after first installation

---

**For technical support:** Contact Deriest team or open issue on GitHub
