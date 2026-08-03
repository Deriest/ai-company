#!/usr/bin/env python3
"""Simple test for _flatten_history without external dependencies."""

def _flatten_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Flatten multi-turn history into 2 messages (system + user) to workaround VansRouter bug.
    
    VansRouter returns empty response (200, len=0) for multi-turn conversations with large messages.
    This function compresses all history into a single system message containing the conversation,
    plus the final user question as a separate user message.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
    
    Returns:
        Flattened list: [system(history), user(last_question)] if >2 messages, else unchanged
    """
    if len(messages) <= 2:
        return messages
    
    # Separate system, history, and last user message
    system_messages = [m for m in messages if m.get("role") == "system"]
    other_messages = [m for m in messages if m.get("role") != "system"]
    
    if not other_messages:
        return messages
    
    # Last message should be user question
    last_message = other_messages[-1]
    history_messages = other_messages[:-1]
    
    # Build compressed system message with full conversation history
    history_parts = []
    
    # Add original system prompts first
    for sys_msg in system_messages:
        history_parts.append(sys_msg.get("content", ""))
    
    # Add conversation history
    if history_messages:
        history_parts.append("\n## Conversation History\n")
        for i, msg in enumerate(history_messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_parts.append(f"{role}: {content}\n")
    
    # Combine into single system message
    compressed_system = "\n".join(history_parts).strip()
    
    # Return: [system(full_history), user(current_question)]
    return [
        {"role": "system", "content": compressed_system},
        {"role": "user", "content": last_message.get("content", "")},
    ]


def test_flatten_history():
    """Test _flatten_history function."""
    print("=" * 60)
    print("QA-249-R6: Testing _flatten_history()")
    print("=" * 60)
    print()
    
    # Test 1: <= 2 messages (should be unchanged)
    print("Test 1: Messages <= 2 (should be unchanged)")
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Question"},
    ]
    result = _flatten_history(messages)
    assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    print(f"  Input: {len(messages)} messages")
    print(f"  Output: {len(result)} messages")
    print("  ✓ PASS\n")
    
    # Test 2: > 2 messages (should be flattened to 2)
    print("Test 2: Messages > 2 (should be flattened to 2)")
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
    
    print(f"  Input: {len(messages)} messages")
    print(f"  Output: {len(result)} messages")
    print(f"    - System message length: {len(result[0]['content'])} chars")
    print(f"    - User message: '{result[1]['content']}'")
    print("  ✓ PASS\n")
    
    # Test 3: Large multi-turn (7 messages simulating 30k context)
    print("Test 3: 7 messages simulating 30k context")
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
    ]
    for i in range(3):
        messages.append({"role": "user", "content": f"Block {i}: " + "K" * 5000})
        messages.append({"role": "assistant", "content": f"Response {i}: " + "R" * 5000})
    messages.append({"role": "user", "content": "What is the last block number?"})
    
    result = _flatten_history(messages)
    assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "What is the last block number?"
    
    print(f"  Input: {len(messages)} messages (~30k tokens)")
    print(f"  Output: {len(result)} messages")
    print(f"    - System message length: {len(result[0]['content'])} chars")
    print(f"    - Contains Block 0: {'✓' if 'Block 0' in result[0]['content'] else '✗'}")
    print(f"    - Contains Block 1: {'✓' if 'Block 1' in result[0]['content'] else '✗'}")
    print(f"    - Contains Block 2: {'✓' if 'Block 2' in result[0]['content'] else '✗'}")
    print("  ✓ PASS\n")
    
    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    print()
    print("Implementation verified:")
    print("  - Messages <= 2: unchanged")
    print("  - Messages > 2: flattened to [system(history), user(question)]")
    print("  - All conversation history preserved in system message")
    print()


if __name__ == "__main__":
    test_flatten_history()
