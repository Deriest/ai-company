# AIC-ADE v2.4.22 — Vision QA Remaining Issues (Round 12)

**Status:** 90% done. 4 remaining issues + 1 missing fix.

## ✅ FIXED & VERIFIED (via vision screenshots)
- ✅ Sidebar: "AICompany ADE" appears correctly
- ✅ Office header: "15 workers · 0 active · 0 missions"
- ✅ Skill Registry cards: header "AICompany ADE" + `- ×` buttons (minus + close)
- ✅ Live Company cards: header "AICompany ADE" + `- ×` buttons (all departments)
- ✅ Observability: 2 tabs (Overview + Graph), context/workers removed, usage merged
- ✅ Command Center: context progress bar "total msg: 0 / 1,000,000"
- ✅ Command Center: build | plan buttons near composer
- ✅ Command Center: no ❯ prefix in input, placeholder = "Type a message…"
- ✅ Command Center: message left-aligned with "> " prefix (no dots)
- ✅ Command Center: status bar = "System operational" (no connected/offline/inspector/Hermes)
- ✅ Version: v2.4.22
- ✅ Logo: /home/tvd/aic-ade-logo.png deployed to build + renderer

## ❌ REMAINING ISSUES (Round 12)

### 1. HTML title still "AIC IDE"
- File: `app/src/renderer/index.html` line 10 → `<title>AIC IDE</title>`
- Should be: `<title>AICompany ADE</title>`
- (The BrowserWindow title in main.ts:354 is already "AICompany ADE" ✅)

### 2. Office page: bottom buttons + right panel clipped
- Bottom buttons ("Start a Mission", "View Workforce", "Command Palette") partially cut off by viewport bottom
- Right panel "Lounge..." clipped on the right edge
- Need to fix overflow/positioning in the Office layout component
- File: `app/src/renderer/src/components/VirtualOfficeCanvas.tsx` or `WorkspaceView.tsx`

### 3. Live Company page: bottom cards clipped
- Engineering department: 5th worker (Pulse) partially hidden
- Platform department: all 4 workers (Nova, Nexus, Flint, Sentinel) completely hidden
- Need to fix viewport height/padding so all 15 workers are visible
- File: `app/src/renderer/src/components/LiveCompanyView.tsx`

### 4. Skills Registry: description text truncated with ellipsis
- Card descriptions show "..." when text is too long
- Minor cosmetic issue — need to allow text to expand or adjust card height
- File: `app/src/renderer/src/components/SkillsView.tsx` or skill card component

## ⚠️ VERIFICATION NEEDED
- Chat functionality: tested via CDP, got "No AI provider configured" error (expected — no provider in fresh profile). Need provider to test actual response. The /chat/stream endpoint works (verified in earlier QA rounds). Windows issue might be same — provider not configured.
- Graph tab: added but no content shown yet (placeholder)

## 🔧 FIX INSTRUCTIONS (for opencode)
1. Fix `app/src/renderer/index.html` line 10 → `<title>AICompany ADE</title>`
2. Fix Office layout: add `overflow: hidden` / adjust padding so bottom buttons + right panel are fully visible
3. Fix Live Company: add scroll or adjust card sizing to fit all 15 workers
4. Fix Skills card: remove text truncation or adjust card height for full description
5. Rebuild: `npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
6. Update latest.json + copy to app/release/
7. DO NOT use subagent/parallel fixer