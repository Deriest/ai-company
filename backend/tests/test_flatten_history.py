"""QA-249-R6: Test flatten_history workaround for VansRouter multi-turn bug."""
import pytest
from llm.provider import _flatten_history


def test_flatten_history_unchanged_when_2_or_less():
    """Test that messages <= 2 are unchanged."""
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Question"},
    ]
    result = _flatten_history(messages)
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert result == messages


def test_flatten_history_compresses_multi_turn():
    """Test that > 2 messages are flattened to 2."""
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
        {"role": "user", "content": "Current question"},
    ]
    result = _flatten_history(messages)
    
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    
    # Verify history is preserved in system message
    assert "Message 1" in result[0]["content"]
    assert "Response 1" in result[0]["content"]
    assert "Message 2" in result[0]["content"]
    assert "Response 2" in result[0]["content"]
    
    # Verify last user message is separate
    assert result[1]["content"] == "Current question"


def test_flatten_history_preserves_all_history():
    """Test that all conversation history is preserved after flattening."""
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Block 0: " + "K" * 1000},
        {"role": "assistant", "content": "Response 0"},
        {"role": "user", "content": "Block 1: " + "K" * 1000},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "What is the last block?"},
    ]
    result = _flatten_history(messages)
    
    assert len(result) == 2
    assert "Block 0" in result[0]["content"]
    assert "Block 1" in result[0]["content"]
    assert "Response 0" in result[0]["content"]
    assert "Response 1" in result[0]["content"]
    assert result[1]["content"] == "What is the last block?"


def test_flatten_history_empty_messages():
    """Test edge case: empty messages list."""
    messages = []
    result = _flatten_history(messages)
    assert result == []


def test_flatten_history_single_message():
    """Test edge case: single message."""
    messages = [{"role": "user", "content": "Hello"}]
    result = _flatten_history(messages)
    assert len(result) == 1
    assert result[0]["content"] == "Hello"


def test_flatten_history_multiple_system_messages():
    """Test that multiple system messages are merged."""
    messages = [
        {"role": "system", "content": "System prompt 1"},
        {"role": "system", "content": "System prompt 2"},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Current question"},
    ]
    result = _flatten_history(messages)
    
    assert len(result) == 2
    assert "System prompt 1" in result[0]["content"]
    assert "System prompt 2" in result[0]["content"]
    assert result[1]["content"] == "Current question"


def test_flatten_history_request_format():
    """Test that flattened result matches expected format for VansRouter workaround.
    
    VansRouter requires: [system(all_history), user(current_question)] to avoid 
    empty response bug with multi-turn conversations.
    """
    # Simulate 30k conversation (7 messages)
    messages = [{"role": "system", "content": "Assistant"}]
    for i in range(3):
        messages.append({"role": "user", "content": f"Block {i}: " + "K" * 5000})
        messages.append({"role": "assistant", "content": f"Response {i}"})
    messages.append({"role": "user", "content": "What is the last block number?"})
    
    result = _flatten_history(messages)
    
    # Verify workaround format: exactly 2 messages
    assert len(result) == 2, "VansRouter workaround requires exactly 2 messages"
    assert result[0]["role"] == "system", "First message must be system"
    assert result[1]["role"] == "user", "Second message must be user"
    
    # Verify all blocks are in system message
    for i in range(3):
        assert f"Block {i}" in result[0]["content"], f"Block {i} missing from history"
    
    # Verify current question is separate
    assert result[1]["content"] == "What is the last block number?"
