# OpenCode Task: AIC-ADE v2.4.39 — Fix context token usage calculation

## Approach
- INVESTIGATE root cause first, THEN fix
- Report root cause + fix in summary
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT modify anything outside this bug

## Bug: Context bar token usage tidak akurat

### Current state
- Context bar shows estimated ~500 tokens for 7 messages
- Actual token usage from 9Router (VansRouter) for minimax-m3:
  - Input: 1,400-1,900 tokens per message
  - Output: 75-190 tokens per message
  - Total: ~1,600-2,100 tokens per message
- So 7 messages should show ~11,000+ tokens, not 500

### Reference
Check the opencode repository at https://github.com/anomalyco/opencode for how token usage is calculated. Look at:
- How opencode tracks token usage per message
- How it displays context usage in the UI
- The formula or method used to count tokens

### Root cause investigation (trace the code path)
1. Trace the chat message flow: UI → `chatApi.executeAgent` → backend `/chat/execute` → LLM provider → response → message storage
2. Check if the LLM provider (AIC endpoint) returns token usage in the response
3. Check the streaming response format - does it include `usage` data?
4. Check how the backend creates messages - does it store `token_count`?
5. Check the `chat.ts` API client - does it capture usage data from the streaming response?
6. Check the ChatView.tsx `handleSend` - does it pass token_count when creating messages?

### Files to investigate
- `app/src/renderer/src/lib/api/chat.ts` — chat API client, streaming response handler
- `app/src/renderer/src/components/ChatView.tsx` — handleSend, context bar display
- `backend/backend/api/routes/chat.py` — backend chat endpoint
- `backend/backend/llm/provider.py` — LLM provider client
- `backend/backend/llm/client.py` — HTTP client for LLM API

### Fix
Implement the correct token usage calculation:
- If the LLM provider returns token usage in the streaming response, capture it
- Store it in the message's `token_count` field
- Display the accumulated token count in the context bar
- If token_count is not available, use a better estimation formula:
  - Input tokens: ~1,500 per message (based on 9Router data)
  - Output tokens: ~150 per message
  - System prompt: ~500 tokens
  - Total: (messages.length × 1,650) + 500

## Build (after fix)
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.40
- Copy to app/release/ + SHA256SUMS