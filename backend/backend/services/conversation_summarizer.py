"""Summarize long conversations to fit context window.

Provides LLM-powered conversation summarization with graceful fallback
to simple truncation when the LLM call fails.
"""
import logging
from typing import TYPE_CHECKING

from backend.services.content_utils import content_to_text, truncate_content

if TYPE_CHECKING:
    from llm.provider import LLMProvider

logger = logging.getLogger("aic.conversation_summarizer")


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return len(text) // 4


async def summarize_conversation(
    messages: list[dict],
    provider: "LLMProvider",
    max_summary_tokens: int = 500,
) -> str:
    """Summarize a conversation into a concise summary.

    Parameters
    ----------
    messages:
        List of message dicts with ``role`` and ``content`` keys.
    provider:
        An LLM provider instance used for the summarization call.
    max_summary_tokens:
        Target maximum token count for the summary.

    Returns
    -------
    str
        A 3-5 sentence summary of the conversation, or a fallback
        extraction if the LLM call fails.
    """
    if not messages:
        return ""

    # Build a transcript (truncate individual messages to avoid huge prompts)
    transcript_parts = []
    for m in messages:
        role = m.get("role", "user")
        content = truncate_content(m.get("content", ""), 800)
        if content.strip():
            transcript_parts.append(f"{role}: {content}")
    transcript = "\n".join(transcript_parts)

    if not transcript.strip():
        return ""

    # If transcript is very short, just return it directly
    if estimate_tokens(transcript) <= max_summary_tokens:
        return transcript

    try:
        result = await provider.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a conversation summarization assistant. "
                        "Summarize the following conversation in 3-5 concise sentences. "
                        "Preserve: key decisions made, code changes discussed, "
                        "open questions, and the current task status. "
                        "Do NOT include filler or pleasantries."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            tier="sprinter",
            temperature=0.2,
            max_tokens=max_summary_tokens * 2,  # Allow some headroom for generation
            purpose="conversation_summarization",
        )
        summary = result.get("content", "").strip()
        if summary:
            logger.info(
                f"Summarized {len(messages)} messages into "
                f"~{estimate_tokens(summary)} tokens"
            )
            return summary
    except Exception as e:
        logger.warning(f"LLM summarization failed, using fallback: {e}")

    # Fallback: extract key lines
    return _fallback_summary(messages, max_summary_tokens)


def _fallback_summary(messages: list[dict], max_tokens: int = 500) -> str:
    """Produce a simple summary by extracting the last N meaningful messages."""
    meaningful = []
    for m in messages:
        role = m.get("role", "user")
        content = content_to_text(m.get("content", "")).strip()
        # Skip very short or empty messages
        if len(content) < 20:
            continue
        # Skip tool results (they're usually too verbose)
        if role == "tool":
            continue
        meaningful.append(f"[{role}] {content[:300]}")

    # Take the last ~10 meaningful lines that fit in max_tokens
    selected = []
    char_budget = max_tokens * 4
    used = 0
    for line in reversed(meaningful):
        if used + len(line) > char_budget:
            break
        selected.append(line)
        used += len(line)

    selected.reverse()
    return "\n".join(selected) if selected else "(no meaningful conversation content)"


async def summarize_if_needed(
    messages: list[dict],
    provider: "LLMProvider",
    token_threshold: int = 10_000,
    max_summary_tokens: int = 500,
) -> list[dict]:
    """Summarize old messages if the conversation exceeds the token threshold.

    Keeps the system message and last 5 messages intact, summarizes everything
    in between.  Returns the original messages if no summarization is needed.

    Parameters
    ----------
    messages:
        Full message list.
    provider:
        LLM provider for summarization.
    token_threshold:
        Only summarize if estimated total tokens exceed this.
    max_summary_tokens:
        Target size for the summary.

    Returns
    -------
    list[dict]
        Condensed message list with old messages replaced by a summary.
    """
    if len(messages) <= 6:
        return messages

    total_text = " ".join(content_to_text(m.get("content", "")) for m in messages)
    total_tokens = estimate_tokens(total_text)

    if total_tokens <= token_threshold:
        return messages

    system_msg = messages[0]
    recent = messages[-5:]
    old_messages = messages[1:-5]

    summary = await summarize_conversation(old_messages, provider, max_summary_tokens)

    condensed = [
        system_msg,
        {
            "role": "system",
            "content": f"Previous conversation summary:\n{summary}",
        },
        *recent,
    ]

    new_tokens = estimate_tokens(
        " ".join(content_to_text(m.get("content", "")) for m in condensed)
    )
    logger.info(
        f"Conversation condensed: {len(messages)} messages ({total_tokens} tokens) "
        f"-> {len(condensed)} messages ({new_tokens} tokens)"
    )

    return condensed
