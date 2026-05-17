"""Multi-model fallback — retry LLM calls with alternative models on provider errors.

When a primary model fails with a retryable error (rate limit, 5xx, timeout),
this module retries with a configurable fallback chain before raising.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from app.services.error_classification import classify_tool_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default fallback chains
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_CHAINS: dict[str, list[str]] = {
    "openai/gpt-4o": ["openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022"],
    "openai/gpt-4o-mini": ["openai/gpt-4o", "anthropic/claude-3-5-haiku-20241022"],
    "anthropic/claude-3-5-sonnet-20241022": ["openai/gpt-4o", "anthropic/claude-3-5-haiku-20241022"],
    "anthropic/claude-3-5-haiku-20241022": ["openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022"],
    "deepseek/deepseek-chat": ["openai/gpt-4o-mini"],
}


def get_fallback_models(
    primary_model: str,
    custom_chain: Optional[list[str]] = None,
) -> list[str]:
    """Get the fallback model chain for a given primary model."""
    if custom_chain:
        return custom_chain
    return DEFAULT_FALLBACK_CHAINS.get(primary_model, [])


# ---------------------------------------------------------------------------
# Retryable error detection
# ---------------------------------------------------------------------------

_RETRYABLE_ERROR_CODES = {
    429,  # Rate limited
    500, 502, 503, 504,  # Server errors
    408,  # Timeout
}

_RETRYABLE_ERROR_STRINGS = [
    "rate limit",
    "too many requests",
    "service unavailable",
    "timeout",
    "timed out",
    "overloaded",
    "capacity",
    "connection",
    "econnreset",
    "econnrefused",
]


def is_retryable_error(error: BaseException) -> bool:
    """Check if an error is retryable (transient provider issue)."""
    classified = classify_tool_error(error)
    return classified.kind == "retry"


# ---------------------------------------------------------------------------
# Fallback-aware LLM call
# ---------------------------------------------------------------------------

async def chat_with_fallback(
    messages: list[dict[str, Any]],
    *,
    model: str,
    fallback_models: Optional[list[str]] = None,
    max_retries: int = 1,
    **kwargs: Any,
) -> Any:
    """Call LLM with automatic fallback to alternative models.

    Tries the primary model first. On retryable failure, tries each
    fallback model in order. Raises the last error if all fail.

    Args:
        messages: Chat messages.
        model: Primary model identifier.
        fallback_models: Optional fallback chain. Defaults to built-in chain.
        max_retries: Retries per model before moving to next.
        **kwargs: Passed to ``llm_service.chat()``.

    Returns:
        LLM response from the first successful model.
    """
    from app.services import llm_service

    chain = [model] + (fallback_models or get_fallback_models(model))
    last_error: Optional[BaseException] = None

    for i, candidate_model in enumerate(chain):
        for attempt in range(max_retries + 1):
            try:
                response = await llm_service.chat(
                    messages,
                    model=candidate_model,
                    **kwargs,
                )
                if i > 0:
                    logger.info(
                        "Model fallback succeeded: %s → %s (attempt %d)",
                        model, candidate_model, attempt + 1,
                    )
                return response

            except Exception as exc:
                last_error = exc

                if not is_retryable_error(exc):
                    # Non-retryable: don't try other models
                    logger.warning(
                        "Non-retryable error from %s: %s",
                        candidate_model, exc,
                    )
                    raise

                logger.warning(
                    "Retryable error from %s (attempt %d/%d): %s",
                    candidate_model, attempt + 1, max_retries + 1, exc,
                )

    # All models exhausted
    if last_error:
        logger.error(
            "All fallback models exhausted for %s (chain: %s)",
            model, " → ".join(chain),
        )
        raise last_error
    raise RuntimeError("No models available in fallback chain")
