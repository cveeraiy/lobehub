"""Provider factory — maps string identifiers to SearchProvider instances."""

from __future__ import annotations

import logging
from typing import Optional

from app.services.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading all providers at startup
_PROVIDER_MAP: dict[str, type[SearchProvider]] | None = None


def _build_map() -> dict[str, type[SearchProvider]]:
    from app.services.search.providers.anspire import AnspireProvider
    from app.services.search.providers.bocha import BochaProvider
    from app.services.search.providers.brave import BraveProvider
    from app.services.search.providers.exa import ExaProvider
    from app.services.search.providers.firecrawl import FirecrawlProvider
    from app.services.search.providers.google import GoogleProvider
    from app.services.search.providers.jina import JinaProvider
    from app.services.search.providers.kagi import KagiProvider
    from app.services.search.providers.search1api import Search1APIProvider
    from app.services.search.providers.searxng import SearXNGProvider
    from app.services.search.providers.serper import SerperProvider
    from app.services.search.providers.tavily import TavilyProvider

    return {
        "anspire": AnspireProvider,
        "bocha": BochaProvider,
        "brave": BraveProvider,
        "exa": ExaProvider,
        "firecrawl": FirecrawlProvider,
        "google": GoogleProvider,
        "jina": JinaProvider,
        "kagi": KagiProvider,
        "search1api": Search1APIProvider,
        "searxng": SearXNGProvider,
        "serper": SerperProvider,
        "tavily": TavilyProvider,
    }


def _get_map() -> dict[str, type[SearchProvider]]:
    global _PROVIDER_MAP
    if _PROVIDER_MAP is None:
        _PROVIDER_MAP = _build_map()
    return _PROVIDER_MAP


def create_provider(name: str) -> SearchProvider:
    """Instantiate a search provider by its identifier string.

    Raises ``ValueError`` if the provider name is unknown.
    """
    provider_map = _get_map()
    cls = provider_map.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown search provider '{name}'. "
            f"Available: {', '.join(sorted(provider_map.keys()))}"
        )
    return cls()


def available_providers() -> list[str]:
    """Return sorted list of registered provider identifiers."""
    return sorted(_get_map().keys())
