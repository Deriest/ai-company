"""Content normalization helpers — handle both string and multimodal list content.

Multimodal messages use OpenAI-style content arrays:
    [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}]

Every backend module that slices/joins/patterns content must normalize through
these helpers so Vision images never crash token estimation, summarization,
intent detection, or context building.
"""


def content_to_text(content) -> str:
    """Normalize str or list content (multimodal) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", "") or item.get("content", "") or "")
        return "\n".join(p for p in parts if p)
    return str(content)


def truncate_content(content, limit: int) -> str:
    """Normalize then truncate content to a character limit."""
    text = content_to_text(content)
    return text[:limit]
