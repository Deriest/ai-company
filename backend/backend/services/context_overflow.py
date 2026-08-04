"""Context overflow handler — auto-summarize, truncate, and split tasks when context is too large.

Strategies (applied in order):
1. Summarize old messages when the conversation is long.
2. Truncate oversized tool results.
3. As a last resort, keep only the most recent messages that fit.
"""
import logging
from typing import TYPE_CHECKING

from backend.services.content_utils import content_to_text, truncate_content

if TYPE_CHECKING:
    from llm.provider import LLMProvider

logger = logging.getLogger("aic.context_overflow")


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate (~4 chars per token). Handles multimodal content."""
    return sum(len(content_to_text(m.get("content", ""))) // 4 for m in messages)


async def summarize_messages(messages: list[dict], provider: "LLMProvider") -> str:
    """Summarize a batch of messages using the LLM.

    Falls back to a simple text extraction when the LLM call fails.
    """
    transcript = "\n".join(
        f"{m.get('role', 'user')}: {truncate_content(m.get('content', ''), 500)}"
        for m in messages
    )

    try:
        result = await provider.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a summarization assistant. "
                        "Concisely summarize the following conversation, "
                        "preserving key decisions, code changes, and open questions. "
                        "Keep the summary under 500 words."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            tier="sprinter",
            temperature=0.2,
            max_tokens=1024,
            purpose="summarization",
        )
        summary = result.get("content", "")
        if summary:
            return summary
    except Exception as e:
        logger.warning(f"LLM summarization failed, using fallback: {e}")

    # Fallback: just concatenate truncated lines
    lines = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content", "") or "")[:200]
        if content:
            lines.append(f"[{role}] {content}")
    return "\n".join(lines[-20:])


async def handle_overflow(
    messages: list[dict],
    max_tokens: int,
    provider: "LLMProvider",
) -> tuple[list[dict], str]:
    """Handle context overflow by summarizing or truncating.

    Parameters
    ----------
    messages:
        The full message list (system + conversation + tool results).
    max_tokens:
        The model's token budget for the prompt.
    provider:
        An LLM provider instance used for summarization calls.

    Returns
    -------
    tuple[list[dict], str]
        A message list that fits within *max_tokens*, and the name of the
        strategy that was applied (``"none"``, ``"summarize"``,
        ``"truncate_tools"``, or ``"keep_recent"``).
    """
    total_tokens = estimate_tokens(messages)

    if total_tokens <= max_tokens:
        return messages, "none"

    logger.info(
        f"Context overflow: {total_tokens} estimated tokens > {max_tokens} budget "
        f"({len(messages)} messages)"
    )

    # ── Strategy 1: Summarize old messages ──────────────────────────
    # Keep system prompt + last 5 messages, summarize everything in between.
    if len(messages) > 10:
        system = messages[0]
        recent = messages[-5:]
        old_messages = messages[1:-5]

        # FIX: OpenAI 400 — `tool` messages must be preceded by an assistant
        # message carrying tool_calls. If the kept window contains tool results,
        # drag the nearest preceding assistant(tool_calls) message into the
        # window (and out of the summarized block) so the pairing is preserved.
        if any(m.get("role") == "tool" for m in recent):
            idx = len(messages) - 6  # index just before the kept window
            while idx >= 1:
                prev = messages[idx]
                if prev.get("role") == "assistant" and prev.get("tool_calls"):
                    recent = [prev] + recent
                    old_messages = [m for m in old_messages if m is not prev]
                    break
                idx -= 1

        summary = await summarize_messages(old_messages, provider)
        condensed = [
            system,
            {
                "role": "system",
                "content": f"Previous conversation summary:\n{summary}",
            },
            *recent,
        ]

        condensed_tokens = estimate_tokens(condensed)
        if condensed_tokens <= max_tokens:
            logger.info(
                f"Strategy 'summarize' applied: {len(messages)} -> {len(condensed)} messages, "
                f"{total_tokens} -> {condensed_tokens} tokens"
            )
            return condensed, "summarize"

        # If still overflowing after summarization, fall through to truncation
        logger.info(
            f"Strategy 'summarize' insufficient ({condensed_tokens} tokens still > {max_tokens}), "
            f"falling through to truncation"
        )
        messages = condensed

    # ── Strategy 2: Truncate tool results ───────────────────────────
    truncated_any = False
    for msg in messages:
        if msg.get("role") == "tool" and len(msg.get("content", "")) > 1000:
            msg["content"] = msg["content"][:1000] + "\n... (truncated)"
            truncated_any = True

    post_truncate_tokens = estimate_tokens(messages)
    if post_truncate_tokens <= max_tokens:
        logger.info(
            f"Strategy 'truncate_tools' applied: "
            f"{'truncated tool results, ' if truncated_any else ''}"
            f"{post_truncate_tokens} tokens now within {max_tokens} budget"
        )
        return messages, "truncate_tools"

    # ── Strategy 3: Keep only the last N messages that fit ──────────
    # Reserve ~100 tokens per message as a rough heuristic.
    keep = max(3, max_tokens // 100)
    truncated = messages[-keep:]
    # FIX: keep tool messages paired with their assistant(tool_calls) message.
    if any(m.get("role") == "tool" for m in truncated):
        idx = len(messages) - keep - 1
        while idx >= 1:
            prev = messages[idx]
            if prev.get("role") == "assistant" and prev.get("tool_calls"):
                truncated = [prev] + truncated
                break
            idx -= 1
    logger.warning(
        f"Strategy 'keep_recent' applied: keeping last {len(truncated)} of "
        f"{len(messages)} messages ({total_tokens} -> {estimate_tokens(truncated)} tokens)"
    )
    return truncated, "keep_recent"
