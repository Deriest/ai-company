# AIC-ADE v2.4.24 — Round 14: Live Company card size fix

## Problem
Live Company page shows 15 workers across 4 departments but the cards are too tall. Engineering worker 5 (Pulse) is partially cut off and Platform department (Nova, Nexus, Flint, Sentinel) is completely hidden.

## Root Cause
The card sizing is too large. Each card takes ~120-150px height. With 5 Engineering workers in 2 rows + 4 Platform workers in 1 row, the total needed height exceeds the available viewport space.

## Fix (specific)
In `app/src/renderer/src/components/LiveCompanyView.tsx`:

1. **Reduce card padding**: Change `p-3` to `p-2` and `gap-2` to `gap-1.5`
2. **Reduce avatar size**: Change `size-10` to `size-8` in the avatar div
3. **Reduce text sizes**: Make the worker name/role text smaller
4. **Remove or minimize the header bar**: The `AICompany ADE + − □ ×` header on each card takes ~30px. Reduce its padding or remove it.
5. **Reduce department spacing**: Change `space-y-4` to `space-y-2` and `mb-3` to `mb-1.5`
6. **Compact the stats bar**: Reduce the stats cards height

## Target
After fix: ALL 15 workers across 4 departments must be visible in the viewport WITHOUT scrolling. The "System operational" footer must be visible at the bottom.

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.25
- Copy to app/release/

## Verification
Launch the built app, onboard, navigate to Live Company, take screenshot, verify ALL 15 workers visible.

DO NOT use subagent/parallel fixer.