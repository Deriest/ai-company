# OpenCode Task: AIC-ADE v2.4.44 → v2.4.45 — Fix chat response disappearing + icon

## Bug 1 — Chat response still disappears
Root cause: `onDone` callback in `handleSend` calls `void loadMessages(convId)` immediately after streaming completes. The API hasn't committed the response yet, so the fetch returns stale data → local state is wiped.

Fix already applied to source:
- `app/src/renderer/src/components/ChatView.tsx` line 822: removed `void loadMessages(convId)` from `onDone`
- Line 700: removed `if (activeId) void loadMessages(activeId)` from `handleStop`
- Line 584: replaced immediate `loadMessages` with `setTimeout(3000)` delay

## Bug 2 — Running app icon still Electron default
Root cause: `BrowserWindow` icon option uses `build/icon.png` (PNG) but on Windows needs `.ico`. Also `build/icon.ico` not in electron-builder `files` list.

Fix:
1. In `package.json`, add `"build/icon.ico"` to `files` array
2. In `src/main/main.ts`, change icon path to use `build/icon.ico` for Windows:
   ```ts
   icon: path.join(__dirname, process.platform === 'win32' ? '../../build/icon.ico' : '../../build/icon.png'),
   ```

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.45
- Copy to app/release/ + SHA256SUMS