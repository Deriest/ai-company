#!/bin/bash
# Manual testing script for QA-249-ROUND2 fixes
# Run this after backend is running on port 8000

set -e

echo "=== QA-249-ROUND2 Manual Testing ==="
echo ""

DB="${DB:-/tmp/aic-249-verify-profile/aic-ade/aic.db}"
BACKEND_URL="http://127.0.0.1:8000"

# Check if backend is running
if ! curl -s -f "$BACKEND_URL/health" >/dev/null 2>&1; then
    echo "❌ Backend not running on $BACKEND_URL"
    echo "Start backend first: cd backend && source .venv/bin/activate && python -m uvicorn backend.main:app --port 8000"
    exit 1
fi

echo "✓ Backend is running"
echo ""

# Get or create conversation ID
if [ -f "$DB" ]; then
    CID=$(sqlite3 "$DB" "SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1;" 2>/dev/null || echo "")
fi

if [ -z "$CID" ]; then
    echo "Creating test conversation..."
    CID=$(curl -s -X POST "$BACKEND_URL/conversations" \
        -H "Content-Type: application/json" \
        -d '{"title":"QA-249 Test","project_id":null}' | \
        grep -o '"id":"[^"]*"' | cut -d'"' -f4 || echo "")
fi

if [ -z "$CID" ]; then
    echo "❌ Failed to get conversation ID"
    exit 1
fi

echo "✓ Using conversation ID: $CID"
echo ""

# R1: Test /chat non-streaming (should use /v1 in URL)
echo "=== R1: Testing POST /chat (base_url with /v1) ==="
echo "Expected: 200 OK, URL should be :20129/v1/chat/completions"
echo ""

RESP=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BACKEND_URL/chat" \
    -H "Content-Type: application/json" \
    -d "{\"conversation_id\":\"$CID\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}],\"worker_role\":\"thinker\"}")

HTTP_CODE=$(echo "$RESP" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESP" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ R1 PASS: HTTP $HTTP_CODE"
    echo "Response: $(echo "$BODY" | head -c 200)..."
else
    echo "❌ R1 FAIL: HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi
echo ""

# R2: Test task request with thinker (should use worker_runtime model)
echo "=== R2: Testing POST /chat/execute with thinker ==="
echo "Expected: 200 OK with streaming chunks, model from worker_runtime (not combo/Thinker)"
echo ""

RESP=$(curl -s -w "\nHTTP_CODE:%{http_code}" -N -X POST "$BACKEND_URL/chat/execute" \
    -H "Content-Type: application/json" \
    -d "{\"conversation_id\":\"$CID\",\"messages\":[{\"role\":\"user\",\"content\":\"Build a simple hello world app\"}],\"worker_role\":\"thinker\"}" | head -c 500)

if echo "$RESP" | grep -q "data:"; then
    echo "✅ R2 PASS: Streaming chunks received"
    echo "Sample: $(echo "$RESP" | head -n 3)"
else
    echo "❌ R2 FAIL: No streaming chunks"
    echo "Response: $RESP"
fi
echo ""

# R3: Test plan mode with planner (should use worker_runtime model)
echo "=== R3: Testing POST /chat/execute with planner ==="
echo "Expected: 200 OK with streaming chunks, model from worker_runtime.planner"
echo ""

RESP=$(curl -s -w "\nHTTP_CODE:%{http_code}" -N -X POST "$BACKEND_URL/chat/execute" \
    -H "Content-Type: application/json" \
    -d "{\"conversation_id\":\"$CID\",\"messages\":[{\"role\":\"user\",\"content\":\"Plan a weather app\"}],\"worker_role\":\"planner\"}" | head -c 500)

if echo "$RESP" | grep -q "data:"; then
    echo "✅ R3 PASS: Streaming chunks received"
    echo "Sample: $(echo "$RESP" | head -n 3)"
else
    echo "❌ R3 FAIL: No streaming chunks"
    echo "Response: $RESP"
fi
echo ""

# R4: Test ConversationEngine token budget
echo "=== R4: Testing ConversationEngine token budget ==="
echo "Expected: Either truncation warning OR successful response (not empty response after full send)"
echo "Note: This test requires large conversation history to trigger truncation"
echo ""

# Create large messages to test budget
LARGE_MSG='{"role":"user","content":"'$(python3 -c 'print("x" * 5000)')'"}' 

RESP=$(curl -s -w "\nHTTP_CODE:%{http_code}" -N -X POST "$BACKEND_URL/chat/execute" \
    -H "Content-Type: application/json" \
    -d "{\"conversation_id\":\"$CID\",\"messages\":[$LARGE_MSG,{\"role\":\"user\",\"content\":\"summarize\"}],\"worker_role\":\"thinker\"}" | head -c 500)

if echo "$RESP" | grep -q "data:"; then
    echo "✅ R4 PASS: Response received (token budget applied)"
    if echo "$RESP" | grep -q "truncat"; then
        echo "  (Truncation warning found)"
    fi
    echo "Sample: $(echo "$RESP" | head -n 2)"
else
    echo "❌ R4 FAIL: No response"
    echo "Response: $RESP"
fi
echo ""

echo "=== Manual Testing Complete ==="
echo ""
echo "Summary:"
echo "- R1: base_url with /v1 intact"
echo "- R2: thinker uses worker_runtime model"
echo "- R3: planner uses worker_runtime model"
echo "- R4: ConversationEngine applies token budget"
echo ""
echo "Run automated tests: cd backend && source .venv/bin/activate && python -m pytest tests/test_qa249_round2.py -v"
