"""Exporter router — export user data as JSON or Markdown."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.message import Message
from app.models.session import Session
from app.models.topic import Topic

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/all")
async def export_all(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Export all user data (agents, sessions, topics, messages) as JSON."""
    agents = (
        await session.execute(select(Agent).where(Agent.user_id == user_id))
    ).scalars().all()
    sessions = (
        await session.execute(select(Session).where(Session.user_id == user_id))
    ).scalars().all()
    topics = (
        await session.execute(select(Topic).where(Topic.user_id == user_id))
    ).scalars().all()
    messages = (
        await session.execute(select(Message).where(Message.user_id == user_id))
    ).scalars().all()

    return {
        "version": 1,
        "agents": [_agent_export(a) for a in agents],
        "sessions": [_session_export(s) for s in sessions],
        "topics": [_topic_export(t) for t in topics],
        "messages": [_msg_export(m) for m in messages],
    }


@router.get("/session/{session_id}/markdown")
async def export_session_markdown(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Export a session's messages as a Markdown conversation."""
    sess = (
        await session.execute(
            select(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
        )
    ).scalar_one_or_none()
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    messages = (
        await session.execute(
            select(Message)
            .where(and_(Message.session_id == session_id, Message.user_id == user_id))
            .order_by(Message.created_at)
        )
    ).scalars().all()

    lines: list[str] = []
    lines.append(f"# {sess.title or 'Untitled Session'}\n")
    for m in messages:
        role_label = {"user": "User", "assistant": "Assistant", "system": "System"}.get(m.role, m.role)
        lines.append(f"## {role_label}\n")
        lines.append(f"{m.content or ''}\n")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.get("/session/{session_id}/json")
async def export_session_json(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Export a single session with its topics and messages."""
    sess = (
        await session.execute(
            select(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
        )
    ).scalar_one_or_none()
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    topics = (
        await session.execute(
            select(Topic).where(and_(Topic.session_id == session_id, Topic.user_id == user_id))
        )
    ).scalars().all()

    messages = (
        await session.execute(
            select(Message)
            .where(and_(Message.session_id == session_id, Message.user_id == user_id))
            .order_by(Message.created_at)
        )
    ).scalars().all()

    return {
        "version": 1,
        "session": _session_export(sess),
        "topics": [_topic_export(t) for t in topics],
        "messages": [_msg_export(m) for m in messages],
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _agent_export(a: Agent) -> dict[str, Any]:
    return {
        "id": a.id,
        "slug": a.slug,
        "title": a.title,
        "description": a.description,
        "systemRole": a.system_role,
        "model": a.model,
        "tags": a.tags,
    }


def _session_export(s: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "type": s.type,
        "title": s.title,
        "description": s.description,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _topic_export(t: Topic) -> dict[str, Any]:
    return {
        "id": t.id,
        "session_id": t.session_id,
        "title": t.title,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _msg_export(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "topic_id": m.topic_id,
        "role": m.role,
        "content": m.content,
        "model": m.model,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
