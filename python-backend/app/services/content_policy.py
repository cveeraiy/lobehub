"""Content policy enforcement — detect and handle policy violations pre/post LLM call.

Two-layer approach:
1. **Error detection** (post-hoc): Detect content policy violations from
   LLM/provider error responses and normalize them into user-friendly messages.
   Port of TS ``contentPolicyError.ts``.

2. **Proactive moderation** (optional, pre-LLM): Check user input against
   OpenAI Moderation API or configurable keyword/regex filters before sending
   to the LLM. Enabled via ``CONTENT_POLICY_ENABLED=true``.

Usage in agent runtime::

    from app.services.content_policy import (
        check_content_pre_llm,
        detect_policy_violation_error,
        ContentPolicyViolation,
    )

    # Pre-LLM check (optional)
    violation = await check_content_pre_llm(messages, config=policy_config)
    if violation:
        raise ContentPolicyViolation(violation.message)

    # Post-LLM error detection
    try:
        response = await llm_service.chat(...)
    except Exception as exc:
        policy_msg = detect_policy_violation_error(exc)
        if policy_msg:
            # Return sanitized message instead of raw provider error
            ...
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERIC_POLICY_MESSAGE = "Content policy check failed. Revise your prompt and try again."

# Provider error codes that indicate content policy violations
_POLICY_ERROR_CODES = frozenset({
    "content_policy_violation",
    "moderation_blocked",
    "InputTextSensitiveContentDetected",
    "content_filter",
    "responsible_ai_policy_violation",
    "content_management_policy",
})

# Keywords in error messages that indicate content policy violations
_POLICY_ERROR_KEYWORDS = [
    "content policy",
    "safety system",
    "sensitive information",
    "content filter",
    "moderation",
    "inappropriate content",
    "violates our policy",
    "content blocked",
    "responsible ai",
    "harmful content",
    "unsafe content",
]

# Default keyword blocklist for proactive filtering (configurable)
_DEFAULT_BLOCKED_PATTERNS: list[str] = [
    # Intentionally empty — populate via CONTENT_POLICY_BLOCKED_PATTERNS env var
    # or pass custom patterns via ContentPolicyConfig
]


# ---------------------------------------------------------------------------
# Content policy violation types
# ---------------------------------------------------------------------------

@dataclass
class ContentPolicyViolation:
    """Represents a detected content policy violation."""

    message: str
    category: str = "unknown"
    severity: str = "medium"  # low, medium, high
    source: str = "unknown"  # "provider_error", "moderation_api", "keyword_filter", "custom"
    flagged_text: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class ContentPolicyViolationError(Exception):
    """Raised when content violates policy — stops execution cleanly."""

    def __init__(
        self,
        message: str = GENERIC_POLICY_MESSAGE,
        violation: Optional[ContentPolicyViolation] = None,
    ) -> None:
        super().__init__(message)
        self.violation = violation or ContentPolicyViolation(
            message=message, source="unknown",
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ContentPolicyConfig:
    """Configuration for content policy enforcement."""

    # Master toggle
    enabled: bool = False

    # Pre-LLM proactive moderation
    use_moderation_api: bool = False
    moderation_model: str = "omni-moderation-latest"
    moderation_api_key: Optional[str] = None

    # Keyword/pattern blocklist
    blocked_patterns: list[str] = field(default_factory=list)
    blocked_patterns_compiled: list[re.Pattern[str]] = field(
        default_factory=list, init=False, repr=False,
    )

    # Category thresholds for moderation API (category → max score)
    # Any category exceeding its threshold triggers a violation
    category_thresholds: dict[str, float] = field(default_factory=lambda: {
        "sexual/minors": 0.1,
        "hate/threatening": 0.3,
        "self-harm/intent": 0.3,
        "self-harm/instructions": 0.3,
        "violence/graphic": 0.5,
        "harassment/threatening": 0.5,
    })

    # Post-LLM output checking
    check_output: bool = True

    def __post_init__(self) -> None:
        if self.blocked_patterns:
            self.blocked_patterns_compiled = [
                re.compile(p, re.IGNORECASE) for p in self.blocked_patterns
            ]


def get_default_config() -> ContentPolicyConfig:
    """Build ContentPolicyConfig from environment variables."""
    blocked_raw = getattr(settings, "content_policy_blocked_patterns", "")
    blocked_list = [p.strip() for p in blocked_raw.split(",") if p.strip()] if blocked_raw else []

    return ContentPolicyConfig(
        enabled=getattr(settings, "content_policy_enabled", False),
        use_moderation_api=getattr(settings, "content_policy_use_moderation_api", False),
        moderation_api_key=getattr(settings, "openai_api_key", None),
        blocked_patterns=blocked_list,
        check_output=getattr(settings, "content_policy_check_output", True),
    )


# ---------------------------------------------------------------------------
# Layer 1: Post-hoc error detection
# ---------------------------------------------------------------------------

def _get_error_code(error: Any) -> Optional[str]:
    """Extract error code from various error shapes."""
    if isinstance(error, dict):
        code = error.get("code") or (error.get("error", {}) or {}).get("code")
        return str(code) if code else None
    return getattr(error, "code", None)


def _get_error_message(error: Any) -> str:
    """Extract error message from various error shapes."""
    if isinstance(error, dict):
        msg = error.get("message") or (error.get("error", {}) or {}).get("message")
        return str(msg) if msg else ""
    if isinstance(error, Exception):
        return str(error)
    return str(error) if error else ""


def detect_policy_violation_error(error: Any) -> Optional[str]:
    """Detect if an error is a content policy violation.

    Mirrors TS ``getContentPolicyErrorMessage()``.

    Returns a user-friendly message if the error is a content policy violation,
    otherwise ``None``.
    """
    error_code = _get_error_code(error)
    error_message = _get_error_message(error).lower()

    # Check known error codes
    if error_code and error_code in _POLICY_ERROR_CODES:
        return GENERIC_POLICY_MESSAGE

    # Check keywords in error message
    for keyword in _POLICY_ERROR_KEYWORDS:
        if keyword in error_message:
            return GENERIC_POLICY_MESSAGE

    return None


def is_content_policy_error(error: Any) -> bool:
    """Check if an error is a content policy violation."""
    return detect_policy_violation_error(error) is not None


# ---------------------------------------------------------------------------
# Layer 2a: Keyword/pattern filter (no external API)
# ---------------------------------------------------------------------------

def check_keyword_filter(
    text: str,
    config: ContentPolicyConfig,
) -> Optional[ContentPolicyViolation]:
    """Check text against keyword/pattern blocklist.

    Returns a violation if any pattern matches, otherwise ``None``.
    """
    if not config.blocked_patterns_compiled:
        return None

    text_lower = text.lower()
    for pattern in config.blocked_patterns_compiled:
        match = pattern.search(text_lower)
        if match:
            return ContentPolicyViolation(
                message=GENERIC_POLICY_MESSAGE,
                category="blocked_pattern",
                severity="high",
                source="keyword_filter",
                flagged_text=match.group(0)[:100],
            )
    return None


# ---------------------------------------------------------------------------
# Layer 2b: OpenAI Moderation API (optional, requires API key)
# ---------------------------------------------------------------------------

async def check_moderation_api(
    text: str,
    config: ContentPolicyConfig,
) -> Optional[ContentPolicyViolation]:
    """Check text against OpenAI Moderation API.

    Returns a violation if any category exceeds its threshold, otherwise ``None``.
    Requires ``config.moderation_api_key`` to be set.
    """
    api_key = config.moderation_api_key
    if not api_key:
        logger.debug("Moderation API check skipped: no API key configured")
        return None

    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/moderations",
                json={"input": text[:10000], "model": config.moderation_model},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Moderation API call failed (non-blocking): %s", exc)
        return None

    results = data.get("results", [])
    if not results:
        return None

    result = results[0]
    if not result.get("flagged"):
        return None

    # Check category scores against thresholds
    categories = result.get("categories", {})
    category_scores = result.get("category_scores", {})

    flagged_categories: list[str] = []
    for cat, flagged in categories.items():
        if flagged:
            threshold = config.category_thresholds.get(cat, 0.8)
            score = category_scores.get(cat, 0.0)
            if score >= threshold:
                flagged_categories.append(f"{cat}({score:.2f})")

    if not flagged_categories:
        # Flagged by API but below our custom thresholds
        return None

    return ContentPolicyViolation(
        message=GENERIC_POLICY_MESSAGE,
        category=flagged_categories[0].split("(")[0],
        severity="high",
        source="moderation_api",
        details={
            "flagged_categories": flagged_categories,
            "model": config.moderation_model,
        },
    )


# ---------------------------------------------------------------------------
# Unified pre-LLM check
# ---------------------------------------------------------------------------

def _extract_user_text(messages: list[dict[str, Any]]) -> str:
    """Extract the most recent user text from messages for moderation check."""
    # Check last few user messages (most relevant for policy check)
    user_texts: list[str] = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                user_texts.append(content)
            elif isinstance(content, list):
                # Multi-part messages (text + images)
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        user_texts.append(part.get("text", ""))
            if len(user_texts) >= 3:
                break

    return "\n".join(reversed(user_texts))


async def check_content_pre_llm(
    messages: list[dict[str, Any]],
    *,
    config: Optional[ContentPolicyConfig] = None,
) -> Optional[ContentPolicyViolation]:
    """Check user input for policy violations before sending to LLM.

    Runs keyword filter first (fast, no network), then moderation API if configured.
    Returns ``None`` if content passes all checks.
    """
    cfg = config or get_default_config()
    if not cfg.enabled:
        return None

    user_text = _extract_user_text(messages)
    if not user_text:
        return None

    # Fast: keyword/pattern check
    violation = check_keyword_filter(user_text, cfg)
    if violation:
        logger.info("Content blocked by keyword filter: category=%s", violation.category)
        return violation

    # Optional: moderation API check
    if cfg.use_moderation_api:
        violation = await check_moderation_api(user_text, cfg)
        if violation:
            logger.info(
                "Content blocked by moderation API: category=%s, details=%s",
                violation.category, violation.details,
            )
            return violation

    return None


async def check_content_post_llm(
    output_text: str,
    *,
    config: Optional[ContentPolicyConfig] = None,
) -> Optional[ContentPolicyViolation]:
    """Check LLM output for policy violations.

    Only runs if ``config.check_output`` is True.
    Returns ``None`` if content passes all checks.
    """
    cfg = config or get_default_config()
    if not cfg.enabled or not cfg.check_output:
        return None

    if not output_text or not output_text.strip():
        return None

    # Fast: keyword/pattern check on output
    violation = check_keyword_filter(output_text, cfg)
    if violation:
        violation.source = "keyword_filter_output"
        logger.info("LLM output blocked by keyword filter: category=%s", violation.category)
        return violation

    # Optional: moderation API check on output
    if cfg.use_moderation_api:
        violation = await check_moderation_api(output_text, cfg)
        if violation:
            violation.source = "moderation_api_output"
            logger.info(
                "LLM output blocked by moderation API: category=%s",
                violation.category,
            )
            return violation

    return None
