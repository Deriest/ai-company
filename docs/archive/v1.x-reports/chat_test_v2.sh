#!/bin/bash
set -e

TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
BASE="http://localhost:8000"

# Create fresh conversation for this test
CONV=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}')
CONV_ID=$(echo "$CONV" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "=== Fresh conversation: $CONV_ID ==="

echo -e "\n=== TEST A: Send 'Hello' ==="
R=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Hello"}')
echo "$R" | python3 -m json.tool 2>/dev/null || echo "RAW: $R"

echo -e "\n=== TEST B: Send 'What can you do?' ==="
R=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"What can you do?"}')
echo "$R" | python3 -m json.tool 2>/dev/null || echo "RAW: $R"

echo -e "\n=== TEST C: Send build request ==="
R=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Build me a React login page with Tailwind"}')
echo "$R" | python3 -m json.tool 2>/dev/null || echo "RAW: $R"

echo -e "\n=== TEST D: Send 'Yes, go ahead' ==="
R=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Yes, go ahead"}')
echo "$R" | python3 -m json.tool 2>/dev/null || echo "RAW: $R"

echo -e "\n=== TEST E: Get all messages (context verification) ==="
MSGS=$(curl -s "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH")
echo "$MSGS" | python3 -c "
import sys,json
msgs = json.load(sys.stdin)
print(f'Total messages: {len(msgs)}')
for m in msgs:
    print(f'  [{m.get(\"role\")}] {str(m.get(\"content\",\"\"))[:200]}')
" 2>&1

echo -e "\n=== TEST F: Tasks created during this conversation ==="
TASKS=$(curl -s "$BASE/api/tasks" -H "$AUTH")
echo "$TASKS" | python3 -c "
import sys,json
data = json.load(sys.stdin)
tasks = data if isinstance(data, list) else data.get('tasks', data.get('items', []))
print(f'Tasks found: {len(tasks)}')
for t in tasks[:10]:
    tid = t.get('id','')
    title = str(t.get('title', t.get('name','')))[:80]
    status = t.get('status','')
    cid = t.get('conversation_id','')
    print(f'  [{tid[:12]}] {title} | status={status} | conv={cid[:12] if cid else \"none\"}')
" 2>&1

echo -e "\n=== TEST G: Verify conversation title was updated ==="
CONV_DETAIL=$(curl -s "$BASE/api/conversations/$CONV_ID" -H "$AUTH")
echo "$CONV_DETAIL" | python3 -m json.tool 2>/dev/null || echo "$CONV_DETAIL"

echo -e "\n=== EDGE CASE 1: Empty message ==="
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":""}')
echo "$R"

echo -e "\n=== EDGE CASE 2: Empty JSON body ==="
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{}')
echo "$R"

echo -e "\n=== EDGE CASE 3: Long message (800 chars) ==="
LONG=$(python3 -c "print('Lorem ipsum dolor sit amet. ' * 30)")
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"content\":\"$LONG\"}")
echo "$R" | tail -3

echo -e "\n=== EDGE CASE 4: Non-existent conversation ==="
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/ffffffffffffffffffffffffffffffff/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"hello"}')
echo "$R"

echo -e "\n=== EDGE CASE 5: No auth token ==="
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H 'Content-Type: application/json' -d '{"content":"hello"}')
echo "$R"

echo -e "\n=== EDGE CASE 6: Duplicate message ==="
R1=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Duplicate test message 12345"}')
echo "First send: $R1" | tail -1
R2=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Duplicate test message 12345"}')
echo "Second send: $R2" | tail -1

echo -e "\n=== EDGE CASE 7: Special characters / injection ==="
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"<script>alert(1)</script> & \"quotes\" and '\''single'\'' and \\n newlines \t tabs"}')
echo "$R" | tail -3

echo -e "\n=== EDGE CASE 8: Send to archived conversation ==="
# Archive the conversation
ARC_CONV=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST "$BASE/api/conversations/batch" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"action\":\"archive\",\"ids\":[\"$ARC_CONV\"]}" > /dev/null
R=$(curl -s -w '\nHTTP_CODE:%{http_code}' -X POST "$BASE/api/conversations/$ARC_CONV/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"hello to archived"}')
echo "Send to archived: $R" | tail -1

echo -e "\n=== BATCH TESTS ==="
# Create conversations for batch testing
B1=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
B2=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
B3=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Batch archive B1,B2:"
curl -s -X POST "$BASE/api/conversations/batch" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"action\":\"archive\",\"ids\":[\"$B1\",\"$B2\"]}" | python3 -m json.tool

echo "Batch delete B3:"
curl -s -X POST "$BASE/api/conversations/batch" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"action\":\"delete\",\"ids\":[\"$B3\"]}" | python3 -m json.tool

echo "Verify B3 is deleted:"
curl -s -w '\nHTTP_CODE:%{http_code}' "$BASE/api/conversations/$B3/messages" -H "$AUTH"

echo -e "\n=== ALL TESTS COMPLETE ==="
