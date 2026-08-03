# OpenCode Task: AIC-ADE v2.4.37 — Fix context usage display

## Context
- Version: 2.4.37 (current)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer
- DO NOT modify anything outside this scope

## Bug: Context usage shows message count, not token count
File: `app/src/renderer/src/components/ChatView.tsx` (line ~1093-1098)

The context bar currently shows `messages.length / contextWindow` (e.g., `4 / 1,000,000`).
It should show accumulated `token_count` from all messages.

### Fix:
1. Replace `messages.length` with `messages.reduce((sum, m) => sum + (m.token_count || 0), 0)` in the context usage display
2. The `MessageRecord` type already has `token_count?: number | null` field
3. If total token_count is 0 (no token data yet), show `?` as fallback
4. Update the progress bar width to use token_count instead of message count

### Current code (line 1093-1098):
```
<span className="font-mono tabular-nums">{messages.length.toLocaleString()}{contextWindow > 0 ? ` / ${contextWindow.toLocaleString()}` : ''}</span>
```
and
```
style={{ width: `${Math.min(100, (messages.length / Math.max(contextWindow, 1)) * 100)}%` }}
```

### Expected result:
- After sending "test" and getting a response with ~500 tokens, context bar shows `~500 / 1,000,000`
- Progress bar reflects token usage percentage

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.38
- Copy to app/release/ + SHA256SUMS