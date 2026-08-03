#!/bin/bash
# QA-249-R5 Manual Testing Script
# Test 30k, 100k, 160k, 240k token conversations

BASE_URL="http://127.0.0.1:8000"

echo "=== QA-249-R5 Manual Verification ==="
echo ""

# Helper function to create conversation with N messages of size S
create_test_conversation() {
    local num_messages=$1
    local message_size=$2
    local label=$3
    
    echo "Creating conversation: $label ($num_messages messages x ~$message_size chars)"
    
    # Create new conversation
    conv_response=$(curl -s -X POST "$BASE_URL/conversations" \
        -H "Content-Type: application/json" \
        -d '{"title":"QA-249-R5 Test: '"$label"'"}')
    
    conv_id=$(echo "$conv_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -z "$conv_id" ]; then
        echo "  ❌ Failed to create conversation"
        return 1
    fi
    
    echo "  Created conversation: $conv_id"
    
    # Generate large message content
    block=$(printf 'X%.0s' $(seq 1 $message_size))
    
    # Add messages to build up context
    for i in $(seq 1 $num_messages); do
        curl -s -X POST "$BASE_URL/chat/stream" \
            -H "Content-Type: application/json" \
            -d '{"conversation_id":"'"$conv_id"'","messages":[{"role":"user","content":"Message '"$i"': '"$block"'"}]}' \
            > /dev/null 2>&1
        
        if [ $((i % 5)) -eq 0 ]; then
            echo -n "."
        fi
    done
    
    echo ""
    echo "  ✓ Built conversation with ~$label context"
    echo "$conv_id"
}

# Test function
test_conversation() {
    local conv_id=$1
    local label=$2
    local expected=$3
    
    echo ""
    echo "=== Testing: $label ==="
    echo "Conversation ID: $conv_id"
    echo "Expected: $expected"
    echo ""
    
    response=$(curl -s -N -X POST "$BASE_URL/chat/stream" \
        -H "Content-Type: application/json" \
        -d '{"conversation_id":"'"$conv_id"'","messages":[{"role":"user","content":"What is the last block number? Brief."}]}' 2>&1)
    
    echo "Response preview:"
    echo "$response" | head -20
    echo ""
    
    # Check for success indicators
    if echo "$response" | grep -q '"type": "chunk"'; then
        echo "✅ PASS: Received streaming chunks"
    elif echo "$response" | grep -qi "context terlalu besar\|mulai sesi baru"; then
        echo "✅ PASS: Received friendly error message (not raw 400)"
    elif echo "$response" | grep -qi "CONTENT_LENGTH_EXCEEDS_THRESHOLD"; then
        echo "❌ FAIL: Raw upstream error leaked to user"
    elif echo "$response" | grep -q '"type": "error"'; then
        error_msg=$(echo "$response" | grep '"error"' | head -1)
        echo "⚠️  ERROR: $error_msg"
    else
        echo "❌ FAIL: Empty or unexpected response"
    fi
    
    echo ""
    echo "Full response:"
    echo "$response"
    echo ""
    echo "---"
}

# Build test conversations
echo "Step 1: Building test conversations..."
echo ""

# 30k: ~8 messages x 4KB each
conv_30k=$(create_test_conversation 8 4000 "30k")

# 100k: ~25 messages x 4KB each  
conv_100k=$(create_test_conversation 25 4000 "100k")

# 160k: ~40 messages x 4KB each
conv_160k=$(create_test_conversation 40 4000 "160k")

# 240k: ~60 messages x 4KB each
conv_240k=$(create_test_conversation 60 4000 "240k")

echo ""
echo "Step 2: Running tests..."
sleep 2

# Run tests
test_conversation "$conv_30k" "30k tokens" "Should stream chunks successfully"
test_conversation "$conv_100k" "100k tokens" "Should stream chunks (not 400 raw)"
test_conversation "$conv_160k" "160k tokens" "Should stream OR friendly error (not empty)"
test_conversation "$conv_240k" "240k tokens" "Should show friendly error (not empty)"

echo ""
echo "=== Test Summary ==="
echo "30k conversation: $conv_30k"
echo "100k conversation: $conv_100k"
echo "160k conversation: $conv_160k"
echo "240k conversation: $conv_240k"
echo ""
echo "Review the output above to verify all acceptance criteria."
