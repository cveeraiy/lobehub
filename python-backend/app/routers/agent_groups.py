"""Agent groups router — folder-like grouping for agents.

Agents reference session_groups via `session_group_id`. This router provides
group CRUD and agent-group assignment in that context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.session import SessionGroup

router = APIRouter(prefix="/api/agent-groups", tags=["Agent Groups"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CreateGroupBody(BaseModel):
    name: str
    sort: int = 0


class UpdateGroupBody(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None


@router.get("")
async def list_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_group_dict(g) for g in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    body: CreateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    group = SessionGroup(
        user_id=user_id,
        name=body.name,
        sort=body.sort,
    )
    session.add(group)
    await session.flush()
    return {"id": group.id}


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    body: UpdateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    stmt = (
        update(SessionGroup)
        .where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Unset group on any agents in this group
    await session.execute(
        update(Agent)
        .where(and_(Agent.session_group_id == group_id, Agent.user_id == user_id))
        .values(session_group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
    )
    return {"ok": True}


@router.put("/{group_id}/agents/{agent_id}")
async def assign_agent_to_group(
    group_id: str,
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Agent)
        .where(and_(Agent.id == agent_id, Agent.user_id == user_id))
        .values(session_group_id=group_id)
    )
    return {"ok": True}


@router.delete("/{group_id}/agents/{agent_id}")
async def remove_agent_from_group(
    group_id: str,
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Agent)
        .where(and_(Agent.id == agent_id, Agent.user_id == user_id, Agent.session_group_id == group_id))
        .values(session_group_id=None)
    )
    return {"ok": True}


@router.get("/{group_id}")
async def get_group_by_id(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    grp = (await session.execute(
        select(SessionGroup).where(
            and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not grp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return _group_dict(grp)


@router.post("/remove-all")
async def remove_all_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Agent).where(Agent.user_id == user_id).values(session_group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(SessionGroup.user_id == user_id)
    )
    return {"ok": True}


class UpdateSortBody(BaseModel):
    sort_map: dict[str, int]


@router.put("/sort")
async def update_group_sort(
    body: UpdateSortBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    for gid, sort_val in body.sort_map.items():
        await session.execute(
            update(SessionGroup)
            .where(and_(SessionGroup.id == gid, SessionGroup.user_id == user_id))
            .values(sort=sort_val)
        )
    return {"ok": True}


def _group_dict(g: SessionGroup) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "sort": g.sort,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
