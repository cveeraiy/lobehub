"""Application entry point — assembles the FastAPI app with all routers and middleware.

Run with:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import engine

# ── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("lobehub")


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Ethos Python Backend v0.1.0")
    logger.info("Database: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else "***")
    yield
    # Shutdown: close shared HTTP client + dispose DB connection pool
    from app.tools._http import close_client
    await close_client()
    await engine.dispose()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Ethos Backend",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

# ── CORS ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ────────────────────────────────────────

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# ── Health check ─────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ── Register routers ────────────────────────────────────────────────
#
# Explicit registry — one line per router module.  To add a new router,
# append its dotted path below.  Comment out a line to disable it.

_ROUTER_MODULES: list[str] = [
    # Auth (must be first — serves /api/auth/* for the SPA)
    "app.routers.auth",
    # Core / infra
    "app.routers.config",
    "app.routers.home",
    "app.routers.recent",
    "app.routers.admin",
    "app.routers.enterprise_ai_policies",
    "app.routers.business",
    "app.routers.openapi_permissions",
    "app.routers.openapi_roles",
    "app.routers.openapi_message_translations",
    "app.routers.openapi_responses",
    "app.routers.oauth_device_flow",
    # User
    "app.routers.user",
    "app.routers.user_memory",
    "app.routers.api_keys",
    "app.routers.usage",
    "app.routers.notifications",
    "app.routers.account_deletion",
    # Agents
    "app.routers.agents",
    "app.routers.agent_groups",
    "app.routers.agent_bot_providers",
    "app.routers.agent_documents",
    "app.routers.agent_document_vfs",
    "app.routers.agent_documents_rest",
    "app.routers.agent_cron_jobs",
    "app.routers.agent_signal",
    "app.routers.agent_notify",
    "app.routers.agent_eval",
    "app.routers.agent_eval_external",
    "app.routers.chat_groups",
    # Sessions / topics / threads / messages
    "app.routers.sessions",
    "app.routers.session_groups",
    "app.routers.topics",
    "app.routers.threads",
    "app.routers.messages",
    # Chat & agent runtime
    "app.routers.chat",
    "app.routers.agent",
    "app.routers.agent_stream",
    "app.routers.ai_agent",
    "app.routers.generation",
    "app.routers.generation_workers",
    "app.routers.generation_topics",
    "app.routers.generation_batches",
    "app.routers.generations",
    "app.routers.image_generation",
    "app.routers.video_generation",
    "app.routers.follow_up",
    "app.routers.ai_chat",
    "app.routers.bot_message",
    "app.routers.bot_webhooks",
    "app.routers.device",
    # Files & knowledge
    "app.routers.file_proxy",
    "app.routers.files",
    "app.routers.upload",
    "app.routers.documents",
    "app.routers.notebook",
    "app.routers.chunks",
    "app.routers.knowledge",
    "app.routers.memory",
    # Tools & skills
    "app.routers.tools",
    "app.routers.plugins",
    "app.routers.skills",
    "app.routers.skill_maintainer",
    "app.routers.mcp",
    "app.routers.klavis",
    # AI infra
    "app.routers.ai_infra",
    "app.routers.webapi",
    "app.routers.cloud_sandbox",
    # Search / market / share
    "app.routers.search",
    "app.routers.web_search",
    "app.routers.market",
    "app.routers.market_discover",
    "app.routers.social",
    "app.routers.share",
    "app.routers.rag_eval",
    # Import / export
    "app.routers.importer",
    "app.routers.exporter",
    # Tasks & briefs
    "app.routers.tasks",
    "app.routers.briefs",
    "app.routers.workflows",
]

for _mod_path in _ROUTER_MODULES:
    try:
        _mod = importlib.import_module(_mod_path)
        app.include_router(_mod.router)  # type: ignore[union-attr]
    except Exception:
        logger.exception("Failed to load router %s", _mod_path)

logger.info("Registered %d routers", len(_ROUTER_MODULES))
