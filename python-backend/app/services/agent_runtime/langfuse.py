"""Langfuse tracing integration for the agent runtime."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def _get_langfuse():
    """Lazy-init Langfuse client."""
    global _langfuse_client
    if _langfuse_client is None and settings.langfuse_enabled:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Langfuse tracing initialized (host=%s)", settings.langfuse_host)
        except Exception:
            logger.warning("Failed to initialize Langfuse", exc_info=True)
    return _langfuse_client


def create_langfuse_handler(
    operation_id: str,
    user_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Any]:
    """Create a Langfuse callback handler for a single operation trace."""
    langfuse = _get_langfuse()
    if langfuse is None:
        return None
    try:
        from langfuse.callback import CallbackHandler
        return CallbackHandler(
            trace_name=f"agent-operation-{operation_id[:8]}",
            trace_id=operation_id,
            user_id=user_id,
            trace_metadata=metadata or {},
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        logger.warning("Failed to create Langfuse handler", exc_info=True)
        return None
