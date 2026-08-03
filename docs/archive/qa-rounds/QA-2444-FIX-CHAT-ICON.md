# OpenCode Task: AIC-ADE v2.4.44 — Fix running app icon (BrowserWindow)

## Bug 1 — Chat response disappears
In `app/src/renderer/src/components/ChatView.tsx` line 582:
```javascript
useEffect(() => { if (activeId) void loadMessages(activeId); else setMessages([]) }, [activeId])
```
When `activeId` changes, `loadMessages` fetches from API (empty) → overwrites local streaming state.
Fix: Add `sending` check:
```javascript
useEffect(() => { 
  if (activeId && !sending) void loadMessages(activeId); 
  else if (!activeId) setMessages([]) 
}, [activeId, sending])
```

## Bug 2 — Running app icon not correct
In `app/src/main/main.ts` line 348, `BrowserWindow` options missing `icon`.
Add: `icon: path.join(__dirname, '../../build/icon.png')` so the running app shows the AIC ADE logo, not the default Electron icon.

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.44
- Copy to app/release/ + SHA256SUMS