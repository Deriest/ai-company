# AIC-ADE v2.6.5 Installation Guide

## Current Status
All build artifacts compiled successfully  
Files uploaded to GitHub Release via API  
GitHub download links temporarily returning 404 (GitHub infrastructure issue)

## IMMEDIATE FIX - Manual Installation

Since GitHub downloads are having issues, you can install directly from the local build:

### Windows Users:
Copy this file directly to your Windows machine and run:
/home/tvd/AI-Company/app/dist/AIC-ADE Setup 2.6.5.exe

### Linux Users:
- AppImage: chmod +x /home/tvd/AI-Company/app/dist/AIC-ADE-2.6.5.AppImage then run it
- DEB: sudo dpkg -i /home/tvd/AI-Company/app/dist/aic-ade_2.6.5_amd64.deb

## What Was Fixed in v2.6.5:
- Blackscreen on startup - Electron configuration corrected
- Update stuck at old version - Publish settings added
- Version detection working correctly
- Auto-update configuration complete

## After Installing v2.6.5 Manually:
Once you install v2.6.5 manually, the auto-update will work normally for future updates.

---
Build Date: 2026-08-12
Version: v2.6.5
