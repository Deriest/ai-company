# OpenCode Task: AIC-ADE v2.4.37 — Fix Command Center composer layout

## Context
- Version: 2.4.37 (current)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT modify anything outside this scope

## Bug: Composer layout wrong — empty space on right, context position wrong

File: `app/src/renderer/src/components/ChatView.tsx` (composer area, lines ~1040-1100)

### Current layout (broken):
Row 1: [BUILD | PLAN] [THINKER: ...] [CRAFTER: ...] [SPRINTER: ...] [Fetch] [Compact] [Context]
Row 2: [textarea]

Right side of Row 1 has empty space because model selectors don't stretch.

### Desired layout:
Row 1: [BUILD | PLAN] [████████████████████████████] [Context 4 / 1,048,576]
Row 2: [THINKER: AIC ▼ | ollama/minimax-m3 ▼] [CRAFTER: AIC ▼ | ollama/minimax-m3 ▼] [SPRINTER: AIC ▼ | ollama/minimax-m3 ▼] [Fetch] [Compact]
Row 3: [textarea]

### Changes:
1. Move BUILD | PLAN buttons to left side of Row 1
2. Progress bar in the middle of Row 1 (wider, ~60% of width)
3. Context text ("4 / 1,048,576") on the right side of Row 1
4. Row 2: THINKER/CRAFTER/SPRINTER dropdowns + Fetch + Compact buttons, stretched to fill width
5. Row 3: textarea as before

### Styling:
- Progress bar should be wider (w-32 or flex-1)
- Context text should be blue (same as BUILD active)
- Right side of both rows should fill available space (no empty gap)
- Use flex-1, justify-between, or grid as needed

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.38
- Copy to app/release/ + SHA256SUMS