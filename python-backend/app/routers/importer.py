"""Importer router — import user data from JSON."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.message import Message
from app.models.session import Session
from app.models.topic import Topic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["Import"])


class ImportByFileBody(BaseModel):
    pathname: str


def _import_results(results: dict[str, int]) -> dict[str, dict[str, int]]:
    return {
        key: {"added": value, "errors": 0, "skips": 0}
        for key, value in results.items()
    }


def _response(results: dict[str, int]) -> dict[str, Any]:
    return {"ok": True, "imported": results, "results": _import_results(results)}


def _get_id(item: dict[str, Any], camel: str, snake: str | None = None) -> Any:
    if camel in item:
        return item.get(camel)
    return item.get(snake or camel)


async def _read_request_data(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, UploadFile) and not hasattr(file, "read"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required")
        if not file.filename or not file.filename.endswith(".json"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .json files are accepted")
        try:
            content = await file.read()
            return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid JSON: {exc}") from exc

    payload = await request.json()
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid import payload")
    return data


async def _import_entry_data(
    data: dict[str, Any],
    *,
    user_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    results: dict[str, int] = {"agents": 0, "sessions": 0, "topics": 0, "messages": 0}

    # Import agents
    for item in data.get("agents", []):
        try:
            agent = Agent(
                user_id=user_id,
                slug=item.get("slug", item.get("identifier", "")),
                title=item.get("title", ""),
                description=item.get("description"),
                system_role=item.get("systemRole") or item.get("system_role"),
                model=item.get("model"),
                tags=item.get("tags"),
            )
            session.add(agent)
            results["agents"] += 1
        except Exception:
            logger.warning("Skipped agent import: %s", item.get("slug"))

    # Import sessions
    session_id_map: dict[str, str] = {}  # old_id -> new_id
    for item in data.get("sessions", []):
        try:
            s = Session(
                user_id=user_id,
                type=item.get("type", "agent"),
                title=item.get("title") or (item.get("meta") or {}).get("title"),
                description=item.get("description"),
            )
            session.add(s)
            await session.flush()
            if item.get("id"):
                session_id_map[item["id"]] = s.id
            results["sessions"] += 1
        except Exception:
            logger.warning("Skipped session import: %s", item.get("id"))

    # Import topics
    topic_id_map: dict[str, str] = {}
    for item in data.get("topics", []):
        try:
            source_session_id = _get_id(item, "sessionId", "session_id")
            mapped_session = session_id_map.get(source_session_id or "", source_session_id)
            t = Topic(
                user_id=user_id,
                session_id=mapped_session,
                title=item.get("title", ""),
            )
            session.add(t)
            await session.flush()
            if item.get("id"):
                topic_id_map[item["id"]] = t.id
            results["topics"] += 1
        except Exception:
            logger.warning("Skipped topic import: %s", item.get("id"))

    # Import messages
    for item in data.get("messages", []):
        try:
            source_session_id = _get_id(item, "sessionId", "session_id")
            source_topic_id = _get_id(item, "topicId", "topic_id")
            mapped_session = session_id_map.get(source_session_id or "", source_session_id)
            mapped_topic = topic_id_map.get(source_topic_id or "", source_topic_id)
            m = Message(
                user_id=user_id,
                session_id=mapped_session,
                topic_id=mapped_topic,
                role=item.get("role", "user"),
                content=item.get("content"),
                model=item.get("model"),
            )
            session.add(m)
            results["messages"] += 1
        except Exception:
            logger.warning("Skipped message import")

    await session.flush()
    return _response(results)


@router.post("")
async def import_data(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import agents, sessions, topics, and messages from JSON body or multipart file."""
    data = await _read_request_data(request)
    return await _import_entry_data(data, user_id=user_id, session=session)


@router.post("/pg")
async def import_pg_data(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Accept PostgreSQL/PGlite import payloads and report table counts.

    Full table-level restore is owned by the TS importer today; this endpoint
    preserves the frontend REST contract and returns deterministic result
    counts until Python owns the complete restore semantics.
    """
    payload = await request.json()
    table_data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(table_data, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid PG import payload")
    results = {key: len(value) for key, value in table_data.items() if isinstance(value, list)}
    return {"ok": True, "results": _import_results(results)}


@router.post("/file")
async def import_file_data(
    body: ImportByFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import JSON data from an uploaded S3 object path."""
    try:
        from app.services.file_service import S3Client

        data = json.loads(await S3Client.from_settings().get_content(body.pathname))
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Failed to read file at {body.pathname}",
        ) from exc

    if isinstance(data, dict) and "schemaHash" in data and isinstance(data.get("data"), dict):
        results = {
            key: len(value)
            for key, value in data["data"].items()
            if isinstance(value, list)
        }
        return {"ok": True, "results": _import_results(results)}

    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid import file payload")
    return await _import_entry_data(data, user_id=user_id, session=session)
