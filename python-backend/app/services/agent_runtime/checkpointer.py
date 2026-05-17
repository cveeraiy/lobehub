"""Checkpointer setup — Postgres-backed or MemorySaver fallback."""

from __future__ import annotations

import asyncio
import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.services.agent_runtime.graph import build_agent_graph

logger = logging.getLogger(__name__)

_checkpointer = None
_checkpointer_lock = asyncio.Lock()


async def get_checkpointer():
    """Get or create the Postgres checkpointer (or MemorySaver fallback)."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    async with _checkpointer_lock:
        if _checkpointer is not None:
            return _checkpointer

        # Try Postgres checkpointer using the same DB
        try:
            # langgraph-checkpoint-postgres needs a raw psycopg connection string
            db_url = settings.database_url
            # Convert asyncpg URL to psycopg format for checkpointer
            pg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            checkpointer = AsyncPostgresSaver.from_conn_string(pg_url)
            await checkpointer.setup()
            _checkpointer = checkpointer
            logger.info("LangGraph checkpointer: Postgres")
        except Exception:
            if not settings.debug:
                logger.error(
                    "Postgres checkpointer failed and debug=False; "
                    "MemorySaver is unsafe for production (state lost on restart)",
                    exc_info=True,
                )
                raise RuntimeError(
                    "Cannot start agent runtime: Postgres checkpointer unavailable. "
                    "Set DEBUG=true to allow in-memory fallback."
                )
            logger.warning("Postgres checkpointer failed, using MemorySaver (debug mode only)", exc_info=True)
            _checkpointer = MemorySaver()

        return _checkpointer


# ---------------------------------------------------------------------------
# Compiled graph singleton
# ---------------------------------------------------------------------------

_compiled_graph = None
_graph_lock = asyncio.Lock()


async def get_compiled_graph():
    """Lazy-compile the agent graph with checkpointer."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    async with _graph_lock:
        if _compiled_graph is not None:
            return _compiled_graph

        checkpointer = await get_checkpointer()
        graph = build_agent_graph()
        _compiled_graph = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_review"],
        )
        logger.info("LangGraph agent graph compiled")
        return _compiled_graph
