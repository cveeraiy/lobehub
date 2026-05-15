"""Feature-flag system compatible with the LobeHub TS frontend.

Flags are read from the ``FEATURE_FLAGS`` env var (via ``settings``).
Format: comma-separated tokens, each prefixed with ``+`` (enable) or ``-`` (disable).
Example::

    FEATURE_FLAGS="+knowledge_base,-market,+admin_panel"

The ``DEFAULT_FEATURE_FLAGS`` dict mirrors the TS ``schema.ts`` defaults.
``get_feature_flags(user_id=...)`` returns the resolved ``FeatureFlagsState``
that the ``GET /api/config`` endpoint can serialise to the SPA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.config import settings


# ── Raw flag definitions (mirrors TS FeatureFlagsSchema defaults) ───
DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "check_updates": True,
    "provider_settings": True,
    "openai_api_key": True,
    "openai_proxy_url": True,
    "api_key_manage": False,
    "edit_agent": True,
    "ai_image": False,
    "speech_to_text": True,
    "token_counter": True,
    "welcome_suggest": True,
    "changelog": True,
    "market": False,
    "knowledge_base": True,
    "rag_eval": False,
    "agent_self_iteration": False,
    "agent_onboarding": False,
    "agent_task": False,
    "auth_captcha": True,
    "cloud_promotion": False,
    "bot_channels": False,
    "resources": False,
    "starter_list": False,
    "admin_panel": False,
    "enterprise_mode": False,
    "commercial_hide_github": False,
    "commercial_hide_docs": False,
}

# All recognised flag names (used for validation in the parser)
_VALID_FLAGS = frozenset(DEFAULT_FEATURE_FLAGS)


def parse_feature_flags(flag_string: str) -> dict[str, bool]:
    """Parse a ``FEATURE_FLAGS`` env-var string into overrides.

    Mirrors the TS ``parseFeatureFlag`` utility:
    - ``+flag_name`` → enable
    - ``-flag_name`` → disable
    - Chinese commas (``，``) are normalised.
    """
    overrides: dict[str, bool] = {}
    if not flag_string:
        return overrides

    tokens = flag_string.strip().replace("\uff0c", ",").split(",")
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token[0] in ("+", "-"):
            key = token[1:]
            if key in _VALID_FLAGS:
                overrides[key] = token[0] == "+"
    return overrides


def get_resolved_flags() -> dict[str, bool]:
    """Merge defaults with env-var overrides and return the final flag dict."""
    overrides = parse_feature_flags(settings.feature_flags)
    merged = {**DEFAULT_FEATURE_FLAGS, **overrides}
    return merged


# ── Mapped state (mirrors TS ``mapFeatureFlagsEnvToState``) ─────────
@dataclass(frozen=True)
class FeatureFlagsState:
    """Boolean state consumed by the SPA's ``/api/config`` response."""

    is_agent_editable: bool = True
    is_enterprise: bool = False

    show_provider: bool = True
    show_openai_api_key: bool = True
    show_openai_proxy_url: bool = True
    show_api_key_manage: bool = False
    show_ai_image: bool = False
    show_changelog: bool = True
    show_cloud_promotion: bool = False
    show_market: bool = False
    show_starter_list: bool = False
    show_admin_panel: bool = False

    enable_check_updates: bool = True
    show_welcome_suggest: bool = True
    enable_knowledge_base: bool = True
    enable_rag_eval: bool = False
    enable_agent_self_iteration: bool = False
    enable_agent_onboarding: bool = False
    enable_agent_task: bool = False
    enable_auth_captcha: bool = True
    enable_stt: bool = True
    enable_bot_channels: bool = False
    enable_resources: bool = False

    hide_github: bool = False
    hide_docs: bool = False


def get_feature_flags(user_id: Optional[str] = None) -> FeatureFlagsState:
    """Resolve feature flags into the state object the SPA expects.

    ``user_id`` is accepted for future per-user flag support (array-based
    flag values, matching the TS ``evaluateFeatureFlag`` logic).  Currently
    all flags are global booleans.
    """
    flags = get_resolved_flags()
    enterprise = flags.get("enterprise_mode", False)

    return FeatureFlagsState(
        is_agent_editable=flags.get("edit_agent", True),
        is_enterprise=enterprise,
        show_provider=False if enterprise else flags.get("provider_settings", True),
        show_openai_api_key=False if enterprise else flags.get("openai_api_key", True),
        show_openai_proxy_url=False if enterprise else flags.get("openai_proxy_url", True),
        show_api_key_manage=flags.get("api_key_manage", False),
        show_ai_image=False if enterprise else flags.get("ai_image", False),
        show_changelog=False if enterprise else flags.get("changelog", True),
        show_cloud_promotion=False if enterprise else flags.get("cloud_promotion", False),
        show_market=False if enterprise else flags.get("market", False),
        show_starter_list=flags.get("starter_list", False),
        show_admin_panel=flags.get("admin_panel", False),
        enable_check_updates=False if enterprise else flags.get("check_updates", True),
        show_welcome_suggest=flags.get("welcome_suggest", True),
        enable_knowledge_base=flags.get("knowledge_base", True),
        enable_rag_eval=False if enterprise else flags.get("rag_eval", False),
        enable_agent_self_iteration=flags.get("agent_self_iteration", False),
        enable_agent_onboarding=flags.get("agent_onboarding", False),
        enable_agent_task=flags.get("agent_task", False),
        enable_auth_captcha=flags.get("auth_captcha", True),
        enable_stt=flags.get("speech_to_text", True),
        enable_bot_channels=flags.get("bot_channels", False),
        enable_resources=flags.get("resources", False),
        hide_github=True if enterprise else flags.get("commercial_hide_github", False),
        hide_docs=flags.get("commercial_hide_docs", False),
    )
