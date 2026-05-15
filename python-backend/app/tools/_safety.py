"""Shared safety utilities for builtin tools.

- SSRF protection (URL validation, private IP blocking)
- Rate limiting (per-user token bucket)
- LIKE wildcard escaping
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)


# ── SSRF Protection ──────────────────────────────────────────────────

# RFC 1918 + link-local + loopback ranges
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS IMDS
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),
]


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/reserved IP range."""
    import socket

    try:
        # Resolve hostname to IPs
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _type, _proto, _canonname, sockaddr in results:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    return True
    except (socket.gaierror, ValueError):
        # Can't resolve → treat as suspicious
        return True
    return False


def validate_url(
    url: str,
    *,
    allow_http: bool = False,
    domain_allowlist: list[str] | None = None,
) -> tuple[bool, str]:
    """Validate a URL for safe external fetching.

    Returns (is_valid, error_message).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    # Scheme check
    allowed_schemes = set(settings.allowed_url_schemes.split(","))
    if allow_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes:
        return False, f"URL scheme '{parsed.scheme}' not allowed. Allowed: {', '.join(sorted(allowed_schemes))}"

    hostname = parsed.hostname or ""
    if not hostname:
        return False, "URL has no hostname"

    # Block private IPs (SSRF protection)
    if _is_private_ip(hostname):
        return False, f"URL hostname '{hostname}' resolves to a private/reserved IP range"

    # Domain allowlist (if configured)
    if domain_allowlist:
        if not any(hostname == d or hostname.endswith(f".{d}") for d in domain_allowlist):
            return False, f"Domain '{hostname}' not in allowlist: {', '.join(domain_allowlist)}"

    return True, ""


def get_skill_import_allowlist() -> list[str] | None:
    """Return skill import domain allowlist from settings (None if empty)."""
    raw = settings.skill_import_domain_allowlist.strip()
    if not raw:
        return None
    return [d.strip() for d in raw.split(",") if d.strip()]


# ── Rate Limiting ────────────────────────────────────────────────────

class _TokenBucket:
    """Simple per-key token bucket rate limiter."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"tokens": 0.0, "last_refill": time.monotonic()}
        )

    def try_consume(self, key: str, max_per_minute: int) -> tuple[bool, float]:
        """Try to consume one token.

        Returns (allowed, retry_after_seconds).
        """
        if max_per_minute <= 0:
            return True, 0.0

        now = time.monotonic()
        bucket = self._buckets[key]
        elapsed = now - bucket["last_refill"]
        # Refill tokens
        refill_rate = max_per_minute / 60.0
        bucket["tokens"] = min(max_per_minute, bucket["tokens"] + elapsed * refill_rate)
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True, 0.0
        else:
            retry_after = (1.0 - bucket["tokens"]) / refill_rate
            return False, retry_after

    def cleanup(self, max_age_seconds: float = 3600.0) -> None:
        """Remove stale entries to prevent memory leaks."""
        now = time.monotonic()
        stale_keys = [
            k for k, v in self._buckets.items()
            if now - v["last_refill"] > max_age_seconds
        ]
        for k in stale_keys:
            del self._buckets[k]


# Singleton rate limiter
_rate_limiter = _TokenBucket()


def check_rate_limit(user_id: str) -> tuple[bool, float]:
    """Check if user can make an external tool call.

    Returns (allowed, retry_after_seconds).
    """
    return _rate_limiter.try_consume(user_id, settings.tool_rate_limit_per_minute)


def check_rate_limit_or_error(user_id: str) -> str | None:
    """Check rate limit and return error JSON string if exceeded, else None."""
    import json

    allowed, retry_after = check_rate_limit(user_id)
    if not allowed:
        return json.dumps({
            "error": "Rate limit exceeded",
            "retry_after_seconds": round(retry_after, 1),
        })
    return None


# ── LIKE Wildcard Escaping ───────────────────────────────────────────

def escape_like(value: str) -> str:
    r"""Escape SQL LIKE wildcards (% and _) for safe use in ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
