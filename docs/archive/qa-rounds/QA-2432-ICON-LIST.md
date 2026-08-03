# AIC-ADE v2.4.32 — Icon File List

## Current icon files
| File | Size | Used for |
|---|---|---|
| `/home/tvd/AI-Company/app/build/icon.png` | 1.89 MB | electron-builder icon (Linux AppImage, Windows exe, deb) |
| `/home/tvd/AI-Company/app/src/renderer/public/aic-ade-logo.png` | 1.89 MB | Sidebar logo (SAME file as build/icon.png) |
| `/home/tvd/aic-ade-logo.png` | 1.89 MB | Source logo (SAME file) |

## Current status
✅ `build/icon.png` = `aic-ade-logo.png` = AIC ADE logo (NOT another logo)
✅ Sidebar logo shows correctly
✅ electron-builder uses `build/icon.png` for all platforms

## Possible issues
1. **Windows .ico format**: electron-builder auto-converts PNG to ICO, but the result might be low quality. Need a proper `.ico` file with multiple sizes (16x16, 32x32, 48x48, 256x256)
2. **File size too large**: 1.89MB PNG is huge for an icon. Should be optimized (512x512 max, compressed)
3. **Windows taskbar icon**: If Windows cached the old icon, it won't update until the app is re-pinned
4. **macOS .icns format**: Not needed (no macOS build)

## Suggested fix
1. Generate optimized icon: 512x512 PNG from the source logo
2. Generate Windows `.ico` with multiple sizes
3. Update `build/icon.png` with the optimized version
4. Rebuild Windows installer