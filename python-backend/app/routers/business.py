"""Self-hosted business/account compatibility endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message

router = APIRouter(prefix="/api", tags=["Business"])


@router.get("/business/subscription")
@router.get("/subscription")
async def get_subscription(_user_id: str = Depends(get_current_user_id)):
    return {
        "plan": "self-hosted",
        "status": "active",
        "subscription": None,
        "usageBasedBilling": False,
    }


@router.get("/business/top-up")
@router.get("/top-up")
async def get_top_up(_user_id: str = Depends(get_current_user_id)):
    return {"balance": 0, "currency": "USD", "enabled": False, "mode": "self-hosted"}


@router.get("/business/spend")
@router.get("/spend")
async def get_spend(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = select(
        func.count().label("message_count"),
        func.coalesce(func.sum(Message.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(Message.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(Message.token_count), 0).label("total_tokens"),
    ).where(
        and_(
            Message.user_id == user_id,
            Message.role == "assistant",
            func.extract("year", Message.created_at) == now.year,
            func.extract("month", Message.created_at) == now.month,
        )
    )
    row = (await session.execute(stmt)).one()
    return {
        "currency": "USD",
        "estimatedCost": 0,
        "inputTokens": row.input_tokens,
        "messageCount": row.message_count,
        "outputTokens": row.output_tokens,
        "totalTokens": row.total_tokens,
    }
