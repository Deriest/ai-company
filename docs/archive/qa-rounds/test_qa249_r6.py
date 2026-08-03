#!/usr/bin/env python3
"""QA-249-R6: Test script for flatten_history workaround.

Tests various conversation sizes to verify VansRouter multi-turn bug is fixed.
"""
import sys
import json
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from storage.database import async_session
from storage.models import Conversation, Message

# Test block size (16KB per message ~4000 tokens)
BLOCK_16K = "K" * 16000

TEST_CASES = [
    {"name": "30k_7msgs", "blocks": 7, "expected": "chunk keluar"},
    {"name": "100k_25msgs", "blocks": 25, "expected": "chunk keluar"},
    {"name": "160k_40msgs", "blocks": 40, "expected": "chunk keluar OR friendly error"},
    {"name": "240k_60msgs", "blocks": 60, "expected": "friendly error"},
]


async def create_test_conversation(db: AsyncSession, num_blocks: int) -> str:
    """Create a conversation with N messages of ~16KB each."""
    conv = Conversation(
        title=f"QA-249-R6 Test: {num_blocks} blocks",
        user_id="test-user",
        context={"test": True, "qa": "249-r6"},
    )
    db.add(conv)
    await db.flush()
    
    # Add history messages
    for i in range(num_blocks):
        msg = Message(
            conversation_id=conv.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Block {i}: {BLOCK_16K}",
        )
        db.add(msg)
    
    await db.commit()
    return conv.id


async def test_flatten_history():
    """Test _flatten_history function directly."""
    from llm.provider import _flatten_history
    
    print("Testing _flatten_history()...")
    
    # Test 1: <= 2 messages (should be unchanged)
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Question"},
    ]
    result = _flatten_history(messages)
    assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
    print("  ✓ Test 1: <= 2 messages unchanged")
    
    # Test 2: > 2 messages (should be flattened to 2)
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
        {"role": "user", "content": "Current question"},
    ]
    result = _flatten_history(messages)
    assert len(result) == 2, f"Expected 2 messages after flatten, got {len(result)}"
    assert result[0]["role"] == "system", "First message should be system"
    assert result[1]["role"] == "user", "Second message should be user"
    assert "Message 1" in result[0]["content"], "History should contain Message 1"
    assert "Response 1" in result[0]["content"], "History should contain Response 1"
    assert result[1]["content"] == "Current question", "Last user message should be preserved"
    print("  ✓ Test 2: > 2 messages flattened to 2")
    print(f"    - System message length: {len(result[0]['content'])} chars")
    print(f"    - User message: '{result[1]['content']}'")
    
    print("✓ All _flatten_history() tests passed\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("QA-249-R6: Flatten History Workaround Test")
    print("=" * 60)
    print()
    
    # Test the flatten function directly
    await test_flatten_history()
    
    # Create test conversations
    print("Creating test conversations...")
    async with async_session() as db:
        for tc in TEST_CASES:
            conv_id = await create_test_conversation(db, tc["blocks"])
            size_kb = tc["blocks"] * 16
            print(f"  ✓ Created {tc['name']}: {conv_id} ({size_kb}KB, {tc['blocks']} messages)")
    
    print()
    print("=" * 60)
    print("Test conversations created. Now test with curl:")
    print("=" * 60)
    print()
    print("# Get conversation IDs from database:")
    print("sqlite3 backend/aic.db \"SELECT id, title FROM conversations WHERE context LIKE '%qa-249-r6%' ORDER BY created_at DESC LIMIT 4;\"")
    print()
    print("# Then test each with:")
    print("curl -s -N -X POST http://127.0.0.1:8000/chat/stream \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"conversation_id\":\"<cid>\",\"messages\":[{\"role\":\"user\",\"content\":\"What is the last block number? Brief.\"}]}'")
    print()
    print("Expected results:")
    for tc in TEST_CASES:
        print(f"  - {tc['name']}: {tc['expected']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
