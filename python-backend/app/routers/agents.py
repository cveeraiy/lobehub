"""Agent CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, asc, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent, AgentKnowledgeBase, AgentFile

router = APIRouter(prefix="/api/agents", tags=["Agents"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateAgentBody(BaseModel):
    slug: str
    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None
    chat_config: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None
    plugins: Optional[list[str]] = None
    opening_message: Optional[str] = None
    opening_questions: Optional[list[str]] = None


class UpdateAgentBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None
    chat_config: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None
    plugins: Optional[list[str]] = None
    pinned: Optional[bool] = None
    opening_message: Optional[str] = None
    opening_questions: Optional[list[str]] = None
    session_group_id: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_agents(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Agent)
        .where(Agent.user_id == user_id)
        .order_by(desc(Agent.pinned), desc(Agent.updated_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_agent_dict(r) for r in rows]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = await _find_agent(session, user_id, agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return _agent_dict(agent)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: CreateAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = Agent(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(agent)
    await session.flush()
    return {"id": agent.id}


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    body: UpdateAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Agent)
        .where(and_(Agent.id == agent_id, Agent.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(AgentKnowledgeBase).where(
            and_(AgentKnowledgeBase.agent_id == agent_id, AgentKnowledgeBase.user_id == user_id)
        )
    )
    await session.execute(
        delete(AgentFile).where(
            and_(AgentFile.agent_id == agent_id, AgentFile.user_id == user_id)
        )
    )
    await session.execute(
        delete(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id))
    )
    return {"ok": True}


# ── Knowledge base links ─────────────────────────────────────────────

@router.post("/{agent_id}/knowledge-bases/{kb_id}", status_code=status.HTTP_201_CREATED)
async def link_kb(
    agent_id: str,
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    link = AgentKnowledgeBase(agent_id=agent_id, knowledge_base_id=kb_id, user_id=user_id)
    session.add(link)
    await session.flush()
    return {"ok": True}


@router.delete("/{agent_id}/knowledge-bases/{kb_id}")
async def unlink_kb(
    agent_id: str,
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(AgentKnowledgeBase).where(
            and_(
                AgentKnowledgeBase.agent_id == agent_id,
                AgentKnowledgeBase.knowledge_base_id == kb_id,
                AgentKnowledgeBase.user_id == user_id,
            )
        )
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_agent(session: AsyncSession, user_id: str, agent_id: str) -> Agent | None:
    stmt = select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id))
    return (await session.execute(stmt)).scalar_one_or_none()


def _agent_dict(a: Agent) -> dict[str, Any]:
    return {
        "id": a.id,
        "slug": a.slug,
        "title": a.title,
        "description": a.description,
        "avatar": a.avatar,
        "system_role": a.system_role,
        "model": a.model,
        "provider": a.provider,
        "tags": a.tags,
        "chat_config": a.chat_config,
        "tts": a.tts,
        "plugins": a.plugins,
        "pinned": a.pinned,
        "opening_message": a.opening_message,
        "opening_questions": a.opening_questions,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
