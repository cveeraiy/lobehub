"""Home router — sidebar agent list and search for the main UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.session import SessionGroup

router = APIRouter(prefix="/api/home", tags=["Home"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/sidebar-agents")
async def get_sidebar_agent_list(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get agents organized by groups for the sidebar.

    Returns pinned agents first, then grouped agents, then ungrouped.
    """
    # Get all groups
    groups_stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort)
    )
    groups = (await session.execute(groups_stmt)).scalars().all()

    # Get all agents
    agents_stmt = (
        select(Agent)
        .where(and_(Agent.user_id == user_id, Agent.virtual.is_(False)))
        .order_by(desc(Agent.pinned), desc(Agent.updated_at))
    )
    agents = (await session.execute(agents_stmt)).scalars().all()

    # Organize by group
    pinned = []
    ungrouped = []
    grouped: dict[str, list[dict[str, Any]]] = {g.id: [] for g in groups}

    for a in agents:
        item = _sidebar_agent(a)
        if a.pinned:
            pinned.append(item)
        elif a.session_group_id and a.session_group_id in grouped:
            grouped[a.session_group_id].append(item)
        else:
            ungrouped.append(item)

    return {
        "pinned": pinned,
        "groups": [
            {
                "id": g.id,
                "items": grouped.get(g.id, []),
                "name": g.name,
                "sort": g.sort,
            }
            for g in groups
        ],
        "ungrouped": ungrouped,
    }


@router.get("/search-agents")
async def search_agents(
    keyword: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Search agents by title or description."""
    pattern = f"%{keyword}%"
    stmt = (
        select(Agent)
        .where(Agent.user_id == user_id)
        .where(
            or_(
                Agent.title.ilike(pattern),
                Agent.description.ilike(pattern),
                Agent.slug.ilike(pattern),
            )
        )
        .order_by(desc(Agent.updated_at))
        .limit(20)
    )
    agents = (await session.execute(stmt)).scalars().all()
    return [_sidebar_agent(a) for a in agents]


class UpdateAgentGroupBody(BaseModel):
    agent_id: str
    session_group_id: Optional[str] = None


@router.put("/agent-group")
async def update_agent_session_group_id(
    body: UpdateAgentGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Move an agent to a different group (or remove from group)."""
    await session.execute(
        update(Agent)
        .where(and_(Agent.id == body.agent_id, Agent.user_id == user_id))
        .values(session_group_id=body.session_group_id)
    )
    return {"ok": True}


def _sidebar_agent(a: Agent) -> dict[str, Any]:
    return {
        "id": a.id,
        "avatar": a.avatar,
        "backgroundColor": a.background_color,
        "description": a.description,
        "heterogeneousType": None,
        "pinned": bool(a.pinned),
        "sessionId": None,
        "title": a.title,
        "type": "agent",
        "updatedAt": a.updated_at.isoformat() if a.updated_at else _now().isoformat(),
    }
