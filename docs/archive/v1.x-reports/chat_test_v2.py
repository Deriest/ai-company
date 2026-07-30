#!/usr/bin/env python3
"""Chat lifecycle test — all API calls via urllib (no deps)."""
import urllib.request, urllib.error, json, sys

BASE = "http://localhost:8000"

def api(method, path, data=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def pp(label, data, code=None):
    prefix = f"[{code}] " if code is not None else ""
    if isinstance(data, (dict, list)):
        print(f"{prefix}{label}: {json.dumps(data, indent=2)[:600]}")
    else:
        print(f"{prefix}{label}: {str(data)[:600]}")

# Login
_, login_resp = api("POST", "/api/auth/login", {"username":"admin","password":"admin123"})
token = login_resp["access_token"]
print(f"Logged in. Token length={len(token)}")

# 1. Create conversation
print("\n" + "=" * 70)
print("1. CREATE CONVERSATION")
code, conv = api("POST", "/api/conversations", {}, token)
print(f"   HTTP {code}")
CONV_ID = conv["id"]
pp("Response", conv)

# 2-5. Multi-turn messages
messages_to_send = [
    "Hello",
    "What can you do?",
    "Build me a React login page with Tailwind",
    "Yes, go ahead",
]

for i, msg in enumerate(messages_to_send, 2):
    print(f"\n{'='*70}")
    print(f"{i}. SEND: '{msg}'")
    code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": msg}, token)
    print(f"   HTTP {code}")
    pp("Response", resp, code)

# 6. Get all messages
print(f"\n{'='*70}")
print("6. GET ALL MESSAGES")
code, msgs = api("GET", f"/api/conversations/{CONV_ID}/messages", token=token)
print(f"   HTTP {code}")
print(f"   Total messages: {len(msgs)}")
for m in msgs:
    role = m.get('role', '?')
    content = str(m.get('content', ''))[:200]
    print(f"   [{role:9s}] {content}")

# 7. Context preservation
print(f"\n{'='*70}")
print("7. CONTEXT PRESERVATION CHECK")
asst = [m for m in msgs if m.get("role") == "assistant"]
print(f"   Assistant messages: {len(asst)}")
has_task_ref = any("task" in (m.get("content","") or "").lower() or "TASK-" in (m.get("content","") or "") for m in asst[1:])
has_code = any(kw in (m.get("content","") or "").lower() for kw in ["import", "function", "const ", "login", "react", "tailwind"] for m in asst)
print(f"   Later responses reference task creation: {has_task_ref}")
print(f"   Code/technical content present: {has_code}")
# Context check: last assistant message should reference build topic
last_asst = asst[-1] if asst else {}
last_content = (last_asst.get("content","") or "").lower()
print(f"   Last assistant msg references build/login: {'login' in last_content or 'react' in last_content or 'tailwind' in last_content or 'import' in last_content}")

# 8. Task creation
print(f"\n{'='*70}")
print("8. TASK CREATION CHECK")
code, tasks_resp = api("GET", "/api/tasks", token=token)
print(f"   HTTP {code}")
tasks = tasks_resp if isinstance(tasks_resp, list) else tasks_resp.get("tasks", tasks_resp.get("items", []))
print(f"   Total tasks: {len(tasks)}")
for t in tasks[:10]:
    tid = str(t.get("id",""))[:12]
    title = str(t.get("title", t.get("name","")))[:80]
    status = t.get("status","")
    cid = str(t.get("conversation_id",""))[:12]
    print(f"   [{tid}] {title} | status={status} | conv={cid}")

# 8b. Conversation title
print(f"\n{'='*70}")
print("8b. CONVERSATION DETAIL")
code, detail = api("GET", f"/api/conversations/{CONV_ID}", token=token)
print(f"   HTTP {code}")
pp("Detail", detail)

# EDGE CASES
print(f"\n{'='*70}")
print("=== EDGE CASES ===")

# EC1: Empty message
print("\nEC1: Empty message")
code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": ""}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

# EC2: Missing content field
print("\nEC2: Missing content field (empty JSON)")
code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

# EC3: Very long message (800 chars)
print("\nEC3: Long message (800 chars)")
long_msg = "Lorem ipsum dolor sit amet. " * 30
code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": long_msg}, token)
print(f"   HTTP {code}")
if code == 200 and isinstance(resp, dict):
    resp_content = resp.get("response", "")
    print(f"   Response content length: {len(resp_content)} chars")
    print(f"   Response preview: {resp_content[:150]}")
else:
    print(f"   Response: {str(resp)[:300]}")

# EC4: Non-existent conversation
print("\nEC4: Non-existent conversation")
code, resp = api("POST", "/api/conversations/ffffffffffffffffffffffffffffffff/messages", {"content": "hello"}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

# EC5: No auth token
print("\nEC5: No auth token")
code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": "hello"})
print(f"   HTTP {code} — {str(resp)[:200]}")

# EC6: Duplicate messages
print("\nEC6: Duplicate message")
code1, r1 = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": "Dup test msg 98765"}, token)
print(f"   First:  HTTP {code1}")
code2, r2 = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": "Dup test msg 98765"}, token)
print(f"   Second: HTTP {code2}")
# Count dupes in history
_, all_msgs = api("GET", f"/api/conversations/{CONV_ID}/messages", token=token)
dupes = [m for m in all_msgs if m.get("content") == "Dup test msg 98765" and m.get("role") == "user"]
print(f"   User messages with that content in history: {len(dupes)} (expected 2 — no dedup guard)")

# EC7: Special chars / XSS
print("\nEC7: Special characters / XSS")
xss = '<script>alert(1)</script> & "quotes" and \\n newlines'
code, resp = api("POST", f"/api/conversations/{CONV_ID}/messages", {"content": xss}, token)
print(f"   HTTP {code}")
if isinstance(resp, dict):
    print(f"   Response contains <script>: {'<script>' in resp.get('response','')}")
    print(f"   Response preview: {resp.get('response','')[:200]}")

# EC8: Send to archived conversation
print("\nEC8: Send to archived conversation")
_, arc = api("POST", "/api/conversations", {}, token)
arc_id = arc["id"]
api("POST", "/api/conversations/batch", {"action":"archive","ids":[arc_id]}, token)
code, resp = api("POST", f"/api/conversations/{arc_id}/messages", {"content": "hello archived"}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

# BATCH OPERATIONS
print(f"\n{'='*70}")
print("=== BATCH OPERATIONS ===")

_, bb1 = api("POST", "/api/conversations", {}, token)
_, bb2 = api("POST", "/api/conversations", {}, token)
_, bb3 = api("POST", "/api/conversations", {}, token)
b1, b2, b3 = bb1["id"], bb2["id"], bb3["id"]

print(f"\nBatch archive b1={b1[:8]}, b2={b2[:8]}:")
code, resp = api("POST", "/api/conversations/batch", {"action":"archive","ids":[b1,b2]}, token)
print(f"   HTTP {code} — {json.dumps(resp)}")

print(f"\nBatch delete b3={b3[:8]}:")
code, resp = api("POST", "/api/conversations/batch", {"action":"delete","ids":[b3]}, token)
print(f"   HTTP {code} — {json.dumps(resp)}")

print(f"\nVerify b3 deleted:")
code, resp = api("GET", f"/api/conversations/{b3}/messages", token=token)
print(f"   HTTP {code} — {str(resp)[:100]}")

# EC9: Invalid batch action
print(f"\nEC9: Invalid batch action")
code, resp = api("POST", "/api/conversations/batch", {"action":"invalid","ids":[b1]}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

# EC10: Empty batch ids
print(f"\nEC10: Empty batch ids")
code, resp = api("POST", "/api/conversations/batch", {"action":"delete","ids":[]}, token)
print(f"   HTTP {code} — {str(resp)[:200]}")

print(f"\n{'='*70}")
print("ALL TESTS COMPLETE")
