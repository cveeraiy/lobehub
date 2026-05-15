"""Application entry point — assembles the FastAPI app with all routers and middleware.

Run with:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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
    logger.info("Starting LobeHub Python Backend v0.1.0")
    logger.info("Database: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else "***")
    yield
    # Shutdown: close shared HTTP client + dispose DB connection pool
    from app.tools._http import close_client
    await close_client()
    await engine.dispose()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="LobeHub Backend",
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

from app.admin import router as admin_router  # noqa: E402
from app.routers.agent import router as agent_router  # noqa: E402
from app.routers.agent_documents import router as agent_documents_router  # noqa: E402
from app.routers.agent_groups import router as agent_groups_router  # noqa: E402
from app.routers.agents import router as agents_router  # noqa: E402
from app.routers.ai_infra import router as ai_infra_router  # noqa: E402
from app.routers.api_keys import router as api_keys_router  # noqa: E402
from app.routers.chat import router as chat_router  # noqa: E402
from app.routers.chunks import router as chunks_router  # noqa: E402
from app.routers.config import router as config_router  # noqa: E402
from app.routers.documents import router as documents_router  # noqa: E402
from app.routers.exporter import router as exporter_router  # noqa: E402
from app.routers.files import router as files_router  # noqa: E402
from app.routers.follow_up import router as follow_up_router  # noqa: E402
from app.routers.generation import router as generation_router  # noqa: E402
from app.routers.home import router as home_router  # noqa: E402
from app.routers.importer import router as importer_router  # noqa: E402
from app.routers.knowledge import router as knowledge_router  # noqa: E402
from app.routers.market import router as market_router  # noqa: E402
from app.routers.mcp import router as mcp_router  # noqa: E402
from app.routers.memory import router as memory_router  # noqa: E402
from app.routers.messages import router as messages_router  # noqa: E402
from app.routers.notebook import router as notebook_router  # noqa: E402
from app.routers.notifications import router as notifications_router  # noqa: E402
from app.routers.plugins import router as plugins_router  # noqa: E402
from app.routers.recent import router as recent_router  # noqa: E402
from app.routers.search import router as search_router  # noqa: E402
from app.routers.session_groups import router as session_groups_router  # noqa: E402
from app.routers.sessions import router as sessions_router  # noqa: E402
from app.routers.share import router as share_router  # noqa: E402
from app.routers.skills import router as skills_router  # noqa: E402
from app.routers.threads import router as threads_router  # noqa: E402
from app.routers.tools import router as tools_router  # noqa: E402
from app.routers.topics import router as topics_router  # noqa: E402
from app.routers.upload import router as upload_router  # noqa: E402
from app.routers.usage import router as usage_router  # noqa: E402
from app.routers.user import router as user_router  # noqa: E402
from app.routers.user_memory import router as user_memory_router  # noqa: E402
from app.routers.web_search import router as web_search_router  # noqa: E402
from app.routers.tasks import router as tasks_router  # noqa: E402
from app.routers.agent_eval import router as agent_eval_router  # noqa: E402
from app.routers.ai_agent import router as ai_agent_router  # noqa: E402
from app.routers.agent_signal import router as agent_signal_router  # noqa: E402
from app.routers.briefs import router as briefs_router  # noqa: E402
from app.routers.agent_cron_jobs import router as agent_cron_jobs_router  # noqa: E402

app.include_router(config_router)
app.include_router(home_router)
app.include_router(recent_router)
app.include_router(user_router)
app.include_router(user_memory_router)
app.include_router(agents_router)
app.include_router(agent_groups_router)
app.include_router(agent_documents_router)
app.include_router(sessions_router)
app.include_router(session_groups_router)
app.include_router(topics_router)
app.include_router(threads_router)
app.include_router(messages_router)
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(notebook_router)
app.include_router(chunks_router)
app.include_router(knowledge_router)
app.include_router(memory_router)
app.include_router(tools_router)
app.include_router(plugins_router)
app.include_router(skills_router)
app.include_router(ai_infra_router)
app.include_router(notifications_router)
app.include_router(api_keys_router)
app.include_router(search_router)
app.include_router(share_router)
app.include_router(generation_router)
app.include_router(follow_up_router)
app.include_router(usage_router)
app.include_router(market_router)
app.include_router(mcp_router)
app.include_router(agent_router)
app.include_router(importer_router)
app.include_router(exporter_router)
app.include_router(admin_router)
app.include_router(web_search_router)
app.include_router(tasks_router)
app.include_router(agent_eval_router)
app.include_router(ai_agent_router)
app.include_router(agent_signal_router)
app.include_router(briefs_router)
app.include_router(agent_cron_jobs_router)
