"""Builtin model/provider catalog.

Mirrors the TS ``model-bank`` package and ``DEFAULT_MODEL_PROVIDER_LIST``.
In the TS codebase the model catalog is maintained as a separate npm package
(``model-bank``).  Here we define a minimal Python-side catalog with the
most popular providers and a representative set of models for each.

The catalog is intentionally **data-only** — no DB access.  The service
layer merges it with per-user DB records.

Extend ``BUILTIN_PROVIDERS`` and ``BUILTIN_MODELS`` as more providers are
onboarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class BuiltinProvider:
    """Static definition of a known AI provider."""

    id: str
    name: str
    description: str = ""
    enabled: bool = False
    sort: int = 0


@dataclass(frozen=True)
class BuiltinModel:
    """Static definition of a known AI model."""

    id: str
    provider_id: str
    display_name: str = ""
    type: str = "chat"  # chat | embedding | tts | stt | image | video
    enabled: bool = False
    context_window_tokens: int = 4096
    abilities: dict[str, Any] = field(default_factory=dict)
    pricing: Optional[dict[str, Any]] = None
    released_at: Optional[str] = None


# ── Builtin Providers (ordered by default sort) ─────────────────────

BUILTIN_PROVIDERS: list[BuiltinProvider] = [
    BuiltinProvider(id="openai", name="OpenAI", sort=0),
    BuiltinProvider(id="anthropic", name="Anthropic", sort=1),
    BuiltinProvider(id="google", name="Google", sort=2),
    BuiltinProvider(id="deepseek", name="DeepSeek", sort=3),
    BuiltinProvider(id="azure", name="Azure OpenAI", sort=4),
    BuiltinProvider(id="ollama", name="Ollama", sort=5),
    BuiltinProvider(id="openrouter", name="OpenRouter", sort=6),
    BuiltinProvider(id="mistral", name="Mistral AI", sort=7),
    BuiltinProvider(id="groq", name="Groq", sort=8),
    BuiltinProvider(id="perplexity", name="Perplexity", sort=9),
    BuiltinProvider(id="togetherai", name="Together AI", sort=10),
    BuiltinProvider(id="fireworksai", name="Fireworks AI", sort=11),
    BuiltinProvider(id="qwen", name="Qwen", sort=12),
    BuiltinProvider(id="zhipu", name="Zhipu AI", sort=13),
    BuiltinProvider(id="moonshot", name="Moonshot AI", sort=14),
    BuiltinProvider(id="minimax", name="Minimax", sort=15),
    BuiltinProvider(id="siliconcloud", name="SiliconCloud", sort=16),
    BuiltinProvider(id="bedrock", name="AWS Bedrock", sort=17),
    BuiltinProvider(id="xai", name="xAI", sort=18),
]

_PROVIDER_INDEX: dict[str, BuiltinProvider] = {p.id: p for p in BUILTIN_PROVIDERS}
_PROVIDER_ORDER: dict[str, int] = {p.id: i for i, p in enumerate(BUILTIN_PROVIDERS)}


def get_builtin_provider(provider_id: str) -> BuiltinProvider | None:
    return _PROVIDER_INDEX.get(provider_id)


def is_builtin_provider(provider_id: str) -> bool:
    return provider_id in _PROVIDER_INDEX


def get_provider_source(provider_id: str) -> str:
    return "builtin" if is_builtin_provider(provider_id) else "custom"


def get_provider_sort_key(provider_id: str) -> int:
    """Return sort order; custom providers sort after all builtins."""
    return _PROVIDER_ORDER.get(provider_id, len(BUILTIN_PROVIDERS) + 999)


# ── Builtin Models (representative subset) ──────────────────────────

BUILTIN_MODELS: list[BuiltinModel] = [
    # OpenAI
    BuiltinModel(id="gpt-4o", provider_id="openai", display_name="GPT-4o", enabled=True,
                 context_window_tokens=128_000,
                 abilities={"vision": True, "functionCall": True, "reasoning": False}),
    BuiltinModel(id="gpt-4o-mini", provider_id="openai", display_name="GPT-4o Mini", enabled=True,
                 context_window_tokens=128_000,
                 abilities={"vision": True, "functionCall": True}),
    BuiltinModel(id="o3-mini", provider_id="openai", display_name="o3-mini", enabled=True,
                 context_window_tokens=200_000,
                 abilities={"reasoning": True, "functionCall": True}),
    BuiltinModel(id="gpt-4.1", provider_id="openai", display_name="GPT-4.1", enabled=True,
                 context_window_tokens=1_000_000,
                 abilities={"vision": True, "functionCall": True}),
    BuiltinModel(id="gpt-4.1-mini", provider_id="openai", display_name="GPT-4.1 Mini", enabled=True,
                 context_window_tokens=1_000_000,
                 abilities={"vision": True, "functionCall": True}),
    BuiltinModel(id="gpt-4.1-nano", provider_id="openai", display_name="GPT-4.1 Nano", enabled=True,
                 context_window_tokens=1_000_000,
                 abilities={"vision": True, "functionCall": True}),

    # Anthropic
    BuiltinModel(id="claude-sonnet-4-20250514", provider_id="anthropic", display_name="Claude Sonnet 4", enabled=True,
                 context_window_tokens=200_000,
                 abilities={"vision": True, "functionCall": True, "reasoning": True}),
    BuiltinModel(id="claude-3-5-haiku-20241022", provider_id="anthropic", display_name="Claude 3.5 Haiku", enabled=True,
                 context_window_tokens=200_000,
                 abilities={"vision": True, "functionCall": True}),

    # Google
    BuiltinModel(id="gemini-2.5-pro-preview-05-06", provider_id="google", display_name="Gemini 2.5 Pro", enabled=True,
                 context_window_tokens=1_000_000,
                 abilities={"vision": True, "functionCall": True, "reasoning": True}),
    BuiltinModel(id="gemini-2.5-flash-preview-04-17", provider_id="google", display_name="Gemini 2.5 Flash", enabled=True,
                 context_window_tokens=1_000_000,
                 abilities={"vision": True, "functionCall": True, "reasoning": True}),

    # DeepSeek
    BuiltinModel(id="deepseek-chat", provider_id="deepseek", display_name="DeepSeek V3", enabled=True,
                 context_window_tokens=64_000,
                 abilities={"functionCall": True}),
    BuiltinModel(id="deepseek-reasoner", provider_id="deepseek", display_name="DeepSeek R1", enabled=True,
                 context_window_tokens=64_000,
                 abilities={"reasoning": True}),

    # xAI
    BuiltinModel(id="grok-3", provider_id="xai", display_name="Grok 3", enabled=True,
                 context_window_tokens=131_072,
                 abilities={"vision": True, "functionCall": True}),
    BuiltinModel(id="grok-3-mini", provider_id="xai", display_name="Grok 3 Mini", enabled=True,
                 context_window_tokens=131_072,
                 abilities={"reasoning": True, "functionCall": True}),

    # Embedding models
    BuiltinModel(id="text-embedding-3-small", provider_id="openai", display_name="Embedding v3 Small",
                 type="embedding", enabled=True, context_window_tokens=8191),
    BuiltinModel(id="text-embedding-3-large", provider_id="openai", display_name="Embedding v3 Large",
                 type="embedding", enabled=True, context_window_tokens=8191),
]

_MODELS_BY_PROVIDER: dict[str, list[BuiltinModel]] = {}
for _m in BUILTIN_MODELS:
    _MODELS_BY_PROVIDER.setdefault(_m.provider_id, []).append(_m)


def get_builtin_models(provider_id: str) -> list[BuiltinModel]:
    """Return builtin models for a provider (empty list for unknown providers)."""
    return _MODELS_BY_PROVIDER.get(provider_id, [])
