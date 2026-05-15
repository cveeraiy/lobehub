"""LLM service — unified chat & embedding interface via litellm.

Wraps ``litellm`` to provide:
- ``chat()`` — streaming & non-streaming chat completions
- ``embed()`` — text embedding via any litellm-supported provider
- Provider credential resolution from the user's key-vault

Usage::

    from app.services.llm_service import chat, embed

    # Streaming
    async for chunk in chat(messages, model="openai/gpt-4o", stream=True):
        print(chunk)

    # Embedding
    vectors = await embed(["hello world"], model="openai/text-embedding-3-small")
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional

import litellm

from app.config import settings

logger = logging.getLogger(__name__)

# Silence litellm's noisy default logging
litellm.suppress_debug_info = True


async def chat(
    messages: list[dict[str, Any]],
    *,
    model: str = "openai/gpt-4o",
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    extra_kwargs: Optional[dict[str, Any]] = None,
) -> Any | AsyncIterator[Any]:
    """Call an LLM via litellm.

    Parameters
    ----------
    messages : list[dict]
        OpenAI-format messages (``role`` + ``content``).
    model : str
        litellm model string, e.g. ``"openai/gpt-4o"``, ``"anthropic/claude-sonnet-4-20250514"``.
    stream : bool
        If ``True`` returns an async iterator of SSE chunks.
    api_key : str | None
        Override API key (from user key-vault).  Falls back to env vars.
    api_base : str | None
        Override base URL (e.g. user's custom proxy).
    extra_kwargs : dict | None
        Additional kwargs forwarded to ``litellm.acompletion``.

    Returns
    -------
    ModelResponse | AsyncIterator[ModelResponseStream]
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    # Credential resolution: explicit > env var > litellm env auto-detect
    if api_key:
        kwargs["api_key"] = api_key
    elif settings.openai_api_key and model.startswith("openai/"):
        kwargs["api_key"] = settings.openai_api_key

    if api_base:
        kwargs["api_base"] = api_base
    elif settings.openai_proxy_url and model.startswith("openai/"):
        kwargs["api_base"] = settings.openai_proxy_url

    # AWS Bedrock: litellm reads AWS_* env vars automatically, but we also
    # pass them explicitly so they work even without env var export.
    if model.startswith("bedrock/"):
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_region:
            kwargs["aws_region_name"] = settings.aws_region

    if extra_kwargs:
        kwargs.update(extra_kwargs)

    # Ensure a timeout so slow providers can't hold connections forever
    kwargs.setdefault("timeout", 300)  # 5 min default

    response = await litellm.acompletion(**kwargs)
    return response


async def embed(
    texts: list[str],
    *,
    model: str = "openai/text-embedding-3-small",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    dimensions: Optional[int] = None,
    timeout: int = 120,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Returns a list of float vectors, one per input text.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "input": texts,
    }
    if api_key:
        kwargs["api_key"] = api_key
    elif settings.openai_api_key and model.startswith("openai/"):
        kwargs["api_key"] = settings.openai_api_key
    if api_base:
        kwargs["api_base"] = api_base
    elif settings.openai_proxy_url and model.startswith("openai/"):
        kwargs["api_base"] = settings.openai_proxy_url
    if dimensions:
        kwargs["dimensions"] = dimensions

    # AWS Bedrock embedding
    if model.startswith("bedrock/"):
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_region:
            kwargs["aws_region_name"] = settings.aws_region

    kwargs["timeout"] = timeout

    response = await litellm.aembedding(**kwargs)
    return [item["embedding"] for item in response.data]


async def resolve_provider_credentials(
    runtime_config: dict[str, Any],
    provider_id: str,
) -> dict[str, Any]:
    """Extract api_key and api_base from the runtime config for a provider.

    Returns a dict with ``api_key`` and optionally ``api_base`` that can be
    spread into ``chat()`` or ``embed()`` kwargs.
    """
    provider_cfg = runtime_config.get(provider_id, {})
    key_vaults = provider_cfg.get("key_vaults", {})
    config = provider_cfg.get("settings", {}) or {}

    creds: dict[str, Any] = {}
    # Common key-vault field names across providers
    for kv_key in ("apiKey", "api_key"):
        if key_vaults.get(kv_key):
            creds["api_key"] = key_vaults[kv_key]
            break

    for base_key in ("baseURL", "baseUrl", "api_base", "endpoint"):
        val = key_vaults.get(base_key) or config.get(base_key)
        if val:
            creds["api_base"] = val
            break

    return creds
