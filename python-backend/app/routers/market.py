"""Marketplace router — browse/search community agents, install from market."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent

router = APIRouter(prefix="/api/market", tags=["Market"])


class InstallAgentBody(BaseModel):
    identifier: str
    title: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


@router.get("/agents")
async def browse_market_agents(
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Browse agents available in the marketplace.

    For now, this returns agents that have a `market_identifier` set,
    indicating they've been published. In the future this would query an
    external market API.
    """
    stmt = select(Agent).where(Agent.market_identifier.isnot(None))
    if keyword:
        pattern = f"%{keyword}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Agent.title.ilike(pattern),
                Agent.description.ilike(pattern),
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_market_agent_dict(a) for a in rows]


@router.post("/agents/install", status_code=status.HTTP_201_CREATED)
async def install_market_agent(
    body: InstallAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Install (fork) an agent from the marketplace into the user's collection."""
    # Check if already installed
    existing = (
        await session.execute(
            select(Agent).where(
                and_(Agent.market_identifier == body.identifier, Agent.user_id == user_id)
            )
        )
    ).scalar_one_or_none()

    if existing:
        return {"id": existing.id, "already_installed": True}

    agent = Agent(
        user_id=user_id,
        slug=body.identifier,
        market_identifier=body.identifier,
        title=body.title,
        description=body.description,
        avatar=body.avatar,
        system_role=body.system_role,
        model=body.model,
        tags=body.tags,
    )
    session.add(agent)
    await session.flush()
    return {"id": agent.id, "already_installed": False}


@router.delete("/agents/{identifier}")
async def uninstall_market_agent(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove a market-installed agent from the user's collection."""
    from sqlalchemy import delete
    await session.execute(
        delete(Agent).where(
            and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
        )
    )
    return {"ok": True}


def _market_agent_dict(a: Agent) -> dict[str, Any]:
    return {
        "identifier": a.market_identifier,
        "title": a.title,
        "description": a.description,
        "avatar": a.avatar,
        "tags": a.tags,
        "model": a.model,
        "author_id": a.user_id,
    }
