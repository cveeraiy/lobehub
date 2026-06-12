"""Exporter router — export user data as JSON or Markdown."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.message import Message
from app.models.session import Session
from app.models.topic import Topic

router = APIRouter(prefix="/api/export", tags=["Export"])


class ExportPdfBody(BaseModel):
    content: str
    session_id: str
    title: str
    topic_id: str | None = None


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


@router.post("/pdf")
async def export_pdf(body: ExportPdfBody):
    """Return a lightweight PDF payload for the frontend download flow."""
    escaped_title = body.title.replace("(", "\\(").replace(")", "\\)")
    escaped_content = body.content[:4000].replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 16 Tf 72 760 Td ({escaped_title}) Tj 0 -28 Td /F1 10 Tf ({escaped_content}) Tj ET"
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        "/MediaBox [0 0 612 792] /Contents 5 0 R >> endobj\n"
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj\n"
        "trailer << /Root 1 0 R >>\n%%EOF"
    )
    return {
        "filename": f"{body.title or 'chat-export'}.pdf",
        "pdf": base64.b64encode(pdf.encode("utf-8")).decode("ascii"),
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
    lines.append(f"# {getattr(sess, 'title', None) or 'Untitled Session'}\n")
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
        "title": getattr(s, "title", None),
        "description": getattr(s, "description", None),
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
