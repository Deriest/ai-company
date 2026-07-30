#!/bin/bash
set -e

TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
CONV_ID="e26f3e452daa4d9c8336a787b4b31351"
BASE="http://localhost:8000"

echo "=== TEST 2: Send 'Hello' ==="
R2=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Hello"}')
echo "$R2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'role={d.get(\"role\")}, content={str(d.get(\"content\",\"\"))[:300]}')" 2>&1 || echo "RAW: $R2"

echo -e "\n=== TEST 3: Send 'What can you do?' ==="
R3=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"What can you do?"}')
echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'role={d.get(\"role\")}, content={str(d.get(\"content\",\"\"))[:300]}')" 2>&1 || echo "RAW: $R3"

echo -e "\n=== TEST 4: Send build request ==="
R4=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Build me a React login page with Tailwind"}')
echo "$R4" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'role={d.get(\"role\")}, content={str(d.get(\"content\",\"\"))[:300]}')" 2>&1 || echo "RAW: $R4"

echo -e "\n=== TEST 5: Send 'Yes, go ahead' ==="
R5=$(curl -s -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Yes, go ahead"}')
echo "$R5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'role={d.get(\"role\")}, content={str(d.get(\"content\",\"\"))[:300]}')" 2>&1 || echo "RAW: $R5"

echo -e "\n=== TEST 6: Get all messages ==="
R6=$(curl -s "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH")
echo "$R6" | python3 -c "
import sys,json
msgs = json.load(sys.stdin)
if isinstance(msgs, list):
    print(f'Total messages: {len(msgs)}')
    for m in msgs:
        print(f'  [{m.get(\"role\")}] {str(m.get(\"content\",\"\"))[:120]}')
else:
    print(f'Unexpected response type: {type(msgs).__name__}')
    print(str(msgs)[:500])
" 2>&1 || echo "RAW: $R6"

echo -e "\n=== TEST 7: Verify context preservation ==="
# Check if assistant responses reference prior conversation
echo "$R6" | python3 -c "
import sys,json
msgs = json.load(sys.stdin)
if isinstance(msgs, list):
    asst_msgs = [m for m in msgs if m.get('role') == 'assistant']
    print(f'Assistant messages count: {len(asst_msgs)}')
    for i, m in enumerate(asst_msgs):
        print(f'  Assistant msg {i+1}: {str(m.get(\"content\",\"\"))[:150]}')
" 2>&1 || echo "RAW: $R6"

echo -e "\n=== TEST 8: Check task creation ==="
R8=$(curl -s "$BASE/api/tasks" -H "$AUTH")
echo "$R8" | python3 -c "
import sys,json
data = json.load(sys.stdin)
tasks = data if isinstance(data, list) else data.get('tasks', data.get('items', []))
print(f'Tasks found: {len(tasks)}')
for t in tasks[:5]:
    print(f'  Task: {str(t.get(\"title\",t.get(\"name\",\"\")))[:100]} status={t.get(\"status\",\"\")}')
" 2>&1 || echo "RAW: $R8"

echo -e "\n=== TEST 9: Edge case - empty message ==="
R9=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":""}')
echo "Empty message: HTTP $R9"

echo -e "\n=== TEST 10: Edge case - very long message (600 chars) ==="
LONG_MSG=$(python3 -c "print('A' * 600)")
R10=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"content\":\"$LONG_MSG\"}")
echo "Long message: HTTP $R10"

echo -e "\n=== TEST 11: Edge case - non-existent conversation ==="
R11=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/00000000000000000000000000000000/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"test"}')
echo "Non-existent conv: HTTP $R11"

echo -e "\n=== TEST 12: Edge case - no auth token ==="
R12=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/$CONV_ID/messages" -H 'Content-Type: application/json' -d '{"content":"test"}')
echo "No auth: HTTP $R12"

echo -e "\n=== TEST 13: Edge case - duplicate message ==="
R13a=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Duplicate test msg"}')
R13b=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/conversations/$CONV_ID/messages" -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Duplicate test msg"}')
echo "Duplicate 1st: HTTP $R13a, 2nd: HTTP $R13b"

# Create extra conversations for batch tests
echo -e "\n=== TEST 14: Batch operations ==="
C2=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
C3=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created C2=$C2, C3=$C3"

# Batch archive
echo "Batch archive C2,C3:"
R14a=$(curl -s -X POST "$BASE/api/conversations/batch" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"action\":\"archive\",\"ids\":[\"$C2\",\"$C3\"]}")
echo "$R14a"

# Create one more for batch delete
C4=$(curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Batch delete C4=$C4:"
R14b=$(curl -s -X POST "$BASE/api/conversations/batch" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"action\":\"delete\",\"ids\":[\"$C4\"]}")
echo "$R14b"

echo -e "\n=== ALL TESTS COMPLETE ==="
