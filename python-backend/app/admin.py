"""Admin endpoints — gated behind the ``require_admin`` dependency.

Provides basic user management and system overview for admins.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_admin
from app.models.message import Message
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateUserBody(BaseModel):
    first_name: Optional[str] = None
    email: Optional[str] = None
    is_onboarded: Optional[bool] = None


# ── User management ──────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """List all users (paginated)."""
    stmt = (
        select(User)
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_user_dict(u) for u in rows]


@router.get("/users/count")
async def user_count(
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(func.count()).select_from(User))
    return {"count": result.scalar_one()}


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _user_dict(user)


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """Return aggregate stats for a user."""
    msg_count = (
        await session.execute(
            select(func.count()).select_from(Message).where(Message.user_id == user_id)
        )
    ).scalar_one()
    session_count = (
        await session.execute(
            select(func.count()).select_from(Session).where(Session.user_id == user_id)
        )
    ).scalar_one()
    topic_count = (
        await session.execute(
            select(func.count()).select_from(Topic).where(Topic.user_id == user_id)
        )
    ).scalar_one()
    return {
        "user_id": user_id,
        "messages": msg_count,
        "sessions": session_count,
        "topics": topic_count,
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserBody,
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    stmt = update(User).where(User.id == user_id).values(**values)
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """Hard-delete a user and all owned data."""
    # Delete owned messages, topics, sessions first (FK order)
    await session.execute(delete(Message).where(Message.user_id == user_id))
    await session.execute(delete(Topic).where(Topic.user_id == user_id))
    await session.execute(delete(Session).where(Session.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    return {"ok": True}


# ── System overview ──────────────────────────────────────────────────

@router.get("/system/stats")
async def system_stats(
    admin_id: str = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """Return global system stats."""
    users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    sessions = (await session.execute(select(func.count()).select_from(Session))).scalar_one()
    messages = (await session.execute(select(func.count()).select_from(Message))).scalar_one()
    topics = (await session.execute(select(func.count()).select_from(Topic))).scalar_one()
    return {
        "users": users,
        "sessions": sessions,
        "messages": messages,
        "topics": topics,
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _user_dict(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "username": u.username,
        "first_name": u.first_name,
        "is_onboarded": u.is_onboarded,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "accessed_at": u.accessed_at.isoformat() if u.accessed_at else None,
    }
