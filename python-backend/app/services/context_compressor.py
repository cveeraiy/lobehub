"""Context compressor — auto-summarize long conversations to stay within token limits.

When the message history exceeds a configurable token threshold, the compressor
condenses older messages into a summary while preserving the system prompt and
recent turns.

This mirrors the TS ``compressionConfig`` behavior in the agent runtime.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token counting (approximate)
# ---------------------------------------------------------------------------

def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return total_chars // 4


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------

DEFAULT_MAX_TOKENS = 100_000  # Compress when total exceeds this
DEFAULT_TARGET_TOKENS = 40_000  # Target token count after compression
DEFAULT_PRESERVE_RECENT = 6  # Always keep last N messages


async def compress_context(
    messages: list[dict[str, Any]],
    *,
    model: str = "openai/gpt-4o-mini",
    api_key: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    preserve_recent: int = DEFAULT_PRESERVE_RECENT,
) -> tuple[list[dict[str, Any]], bool]:
    """Compress message history if it exceeds the token threshold.

    Returns:
        (compressed_messages, was_compressed)
    """
    estimated = _estimate_tokens(messages)
    if estimated <= max_tokens:
        return messages, False

    logger.info(
        "Context compression triggered: ~%d tokens (max=%d, target=%d)",
        estimated, max_tokens, target_tokens,
    )

    # Separate system messages, recent messages, and compressible middle
    system_messages: list[dict[str, Any]] = []
    other_messages: list[dict[str, Any]] = []

    for msg in messages:
        if msg.get("role") == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)

    if len(other_messages) <= preserve_recent:
        # Too few messages to compress
        return messages, False

    # Split into compressible and preserved
    to_compress = other_messages[:-preserve_recent]
    to_preserve = other_messages[-preserve_recent:]

    if not to_compress:
        return messages, False

    # Build summary prompt
    conversation_text = _format_for_summary(to_compress)

    summary = await _generate_summary(
        conversation_text,
        model=model,
        api_key=api_key,
        target_tokens=target_tokens,
    )

    # Reconstruct messages with summary replacing compressed portion
    summary_message: dict[str, Any] = {
        "role": "system",
        "content": f"[Context Summary — condensed from {len(to_compress)} earlier messages]\n\n{summary}",
    }

    compressed = system_messages + [summary_message] + to_preserve

    final_tokens = _estimate_tokens(compressed)
    logger.info(
        "Context compressed: %d messages → %d messages, ~%d → ~%d tokens",
        len(messages), len(compressed), estimated, final_tokens,
    )

    return compressed, True


def _format_for_summary(messages: list[dict[str, Any]]) -> str:
    """Format messages into a plain-text conversation for summarization."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            # Tool call messages
            if msg.get("tool_calls"):
                tool_names = [tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"]]
                content = f"[Called tools: {', '.join(tool_names)}]"
            elif role == "tool":
                tool_id = msg.get("tool_call_id", "")
                content = f"[Tool result for {tool_id}]: {str(content)[:500]}"
            else:
                continue

        # Truncate very long individual messages
        if len(content) > 2000:
            content = content[:2000] + "..."

        parts.append(f"{role.upper()}: {content}")

    return "\n\n".join(parts)


async def _generate_summary(
    conversation_text: str,
    *,
    model: str = "openai/gpt-4o-mini",
    api_key: Optional[str] = None,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
) -> str:
    """Generate a summary of the conversation text using the LLM."""
    from app.services import llm_service

    # Truncate input to avoid exceeding model context
    max_input_chars = target_tokens * 8  # Generous limit
    if len(conversation_text) > max_input_chars:
        conversation_text = conversation_text[:max_input_chars] + "\n\n[... truncated ...]"

    summary_prompt = [
        {
            "role": "system",
            "content": (
                "You are a conversation summarizer. Produce a concise but comprehensive "
                "summary of the following conversation. Preserve:\n"
                "- Key decisions and conclusions\n"
                "- Important facts and data points\n"
                "- Tool results and their outcomes\n"
                "- User preferences and requirements\n"
                "- Any pending or unresolved items\n\n"
                "Be concise. Use bullet points where appropriate. Do not add commentary."
            ),
        },
        {
            "role": "user",
            "content": f"Summarize this conversation:\n\n{conversation_text}",
        },
    ]

    try:
        response = await llm_service.chat(
            summary_prompt,
            model=model,
            stream=False,
            temperature=0.3,
            max_tokens=min(target_tokens, 4000),
            api_key=api_key,
        )
        choice = response.choices[0]
        return choice.message.content or "[Summary generation failed]"
    except Exception as exc:
        logger.warning("Context compression LLM call failed: %s", exc)
        # Fallback: simple truncation
        return f"[Auto-summary unavailable. Earlier conversation had {len(conversation_text)} chars of context.]"
