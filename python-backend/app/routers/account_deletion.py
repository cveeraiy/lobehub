"""Account deletion workflow router."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.user import User

router = APIRouter(prefix="/api/account-deletion", tags=["Account Deletion"])


class ConfirmDeletionBody(BaseModel):
    confirm: str


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/status")
async def get_account_deletion_status(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    request_state = (user.preference or {}).get("accountDeletion") if user else None
    return {"requested": bool(request_state and request_state.get("requestedAt")), "request": request_state}


@router.post("/request")
async def request_account_deletion(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    preference = dict(user.preference or {})
    preference["accountDeletion"] = {"requestedAt": _now_iso(), "status": "requested"}
    await session.execute(update(User).where(User.id == user_id).values(preference=preference, updated_at=_now()))
    return {"requested": True, "request": preference["accountDeletion"]}


@router.post("/cancel")
async def cancel_account_deletion(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    preference = dict(user.preference or {})
    account_deletion = dict(preference.get("accountDeletion") or {})
    account_deletion.update({"canceledAt": _now_iso(), "status": "canceled"})
    preference["accountDeletion"] = account_deletion
    await session.execute(update(User).where(User.id == user_id).values(preference=preference, updated_at=_now()))
    return {"requested": False, "request": account_deletion}


@router.delete("/confirm")
async def confirm_account_deletion(
    body: ConfirmDeletionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.confirm != "DELETE":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm must be DELETE")
    deleted = await _delete_user_owned_rows(session, user_id)
    return {"deleted": deleted, "success": True, "userId": user_id}


async def _delete_user_owned_rows(session: AsyncSession, user_id: str) -> dict[str, int]:
    from sqlmodel import SQLModel

    deleted: dict[str, int] = {}
    user_columns = {
        "assignee_user_id",
        "author_user_id",
        "created_by_user_id",
        "creator",
        "deleted_by_user_id",
        "shared_with_user_id",
        "user_id",
    }
    for table in reversed(SQLModel.metadata.sorted_tables):
        if table.name == "users":
            continue
        matching = [table.c[name] for name in user_columns if name in table.c]
        if not matching:
            continue
        result = await session.execute(delete(table).where(or_(*(column == user_id for column in matching))))
        if result.rowcount:
            deleted[table.name] = int(result.rowcount)

    result = await session.execute(delete(User).where(User.id == user_id))
    deleted["users"] = int(result.rowcount or 0)
    return deleted


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
