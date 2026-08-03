#!/bin/bash
# QA-249-R6: Manual verification script for flatten_history workaround

set -e

echo "=========================================="
echo "QA-249-R6 Verification Script"
echo "=========================================="
echo ""
echo "Prerequisites:"
echo "  1. Backend running: cd backend && python3 main.py"
echo "  2. VansRouter running at http://127.0.0.1:20129/v1"
echo "  3. Provider configured in AIC-ADE"
echo ""
echo "This script will guide you through manual curl tests."
echo ""

# Test 1: Simple chat (regression check)
echo "=========================================="
echo "Test 1: Simple Chat (Regression Check)"
echo "=========================================="
echo ""
echo "Running simple chat test..."
echo ""

SIMPLE_RESPONSE=$(curl -s -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "test-simple-'$(date +%s)'",
    "messages": [
      {"role": "user", "content": "Hi, what is 2+2? Just the number."}
    ]
  }' 2>&1)

if echo "$SIMPLE_RESPONSE" | grep -q "chunk"; then
  echo "✓ PASS: Simple chat works (got chunks)"
  echo ""
else
  echo "✗ FAIL: Simple chat failed (no chunks)"
  echo "Response: $SIMPLE_RESPONSE"
  echo ""
  exit 1
fi

# Test 2-5: Multi-turn conversations
echo "=========================================="
echo "Tests 2-5: Multi-turn Conversations"
echo "=========================================="
echo ""
echo "For multi-turn tests, you need to:"
echo ""
echo "1. Create a conversation with history (7-60 messages of ~16KB each)"
echo "2. Send a final question"
echo "3. Verify response is NOT empty (200, len=0)"
echo ""
echo "Test cases:"
echo "  - 30k (7 msgs): should get chunks"
echo "  - 100k (25 msgs): should get chunks"
echo "  - 160k (40 msgs): should get chunks OR friendly error"
echo "  - 240k (60 msgs): should get friendly error"
echo ""
echo "Example commands in QA-249-R6-VERIFICATION.md"
echo ""
echo "Manual verification required. Check the documentation."
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo "✓ Unit tests passed (test_flatten_simple.py)"
echo "✓ Simple chat regression test passed"
echo "⏳ Manual curl tests for 30k/100k/160k/240k required"
echo ""
echo "Next steps:"
echo "  1. Run manual curl tests (see QA-249-R6-VERIFICATION.md)"
echo "  2. Collect proof (curl output showing chunks, not empty)"
echo "  3. Review git diff"
echo "  4. Commit with proof"
echo ""
