# OpenCode Task: AIC-ADE v2.4.43 — Fix chat response disappearing

## Bug
When user sends a chat message, the LLM response appears briefly (~1s) then disappears. The messages state is being overwritten by `loadMessages()` API fetch.

## Root cause
In `app/src/renderer/src/components/ChatView.tsx` line 582:
```javascript
useEffect(() => { if (activeId) void loadMessages(activeId); else setMessages([]) }, [activeId])
```
When `activeId` changes (e.g., after creating a new conversation for the message), `loadMessages` fetches messages from the API. But the streaming response hasn't been committed to the API yet, so it returns empty → local messages state is cleared.

## Fix
Skip `loadMessages` when there's an active streaming response in progress. Add a `sending` check:
```javascript
useEffect(() => { 
  if (activeId && !sending) void loadMessages(activeId); 
  else if (!activeId) setMessages([]) 
}, [activeId, sending])
```

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.44
- Copy to app/release/ + SHA256SUMS