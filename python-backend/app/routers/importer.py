"""Importer router — import user data from JSON."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.message import Message
from app.models.session import Session
from app.models.topic import Topic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["Import"])


@router.post("")
async def import_data(
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import agents, sessions, topics, and messages from a JSON file.

    Expected JSON structure::

        {
          "version": 1,
          "agents": [...],
          "sessions": [...],
          "topics": [...],
          "messages": [...]
        }
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .json files are accepted")

    try:
        content = await file.read()
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid JSON: {exc}")

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
                title=item.get("title"),
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
            mapped_session = session_id_map.get(item.get("session_id", ""), item.get("session_id"))
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
            mapped_session = session_id_map.get(item.get("session_id", ""), item.get("session_id"))
            mapped_topic = topic_id_map.get(item.get("topic_id", ""), item.get("topic_id"))
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
    return {"ok": True, "imported": results}
