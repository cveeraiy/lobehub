"""Usage router — token/cost analytics derived from message records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, cast, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message

router = APIRouter(prefix="/api/usage", tags=["Usage"])


@router.get("/by-month")
async def find_by_month(
    month: Optional[str] = Query(default=None, description="YYYY-MM format"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get usage totals for a given month (defaults to current month).

    Returns total messages, token counts, grouped by model.
    """
    if month:
        year, mo = month.split("-")
        year_int, month_int = int(year), int(mo)
    else:
        now = datetime.now(timezone.utc)
        year_int, month_int = now.year, now.month

    stmt = (
        select(
            Message.model,
            func.count().label("message_count"),
            func.coalesce(func.sum(Message.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(Message.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(Message.token_count), 0).label("total_tokens"),
        )
        .where(
            and_(
                Message.user_id == user_id,
                Message.role == "assistant",
                extract("year", Message.created_at) == year_int,
                extract("month", Message.created_at) == month_int,
            )
        )
        .group_by(Message.model)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "model": row.model,
            "message_count": row.message_count,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_tokens": row.total_tokens,
        }
        for row in rows
    ]


@router.get("/by-day")
async def find_and_group_by_day(
    month: Optional[str] = Query(default=None, description="YYYY-MM format"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get daily usage breakdown for the specified month."""
    if month:
        year, mo = month.split("-")
        year_int, month_int = int(year), int(mo)
    else:
        now = datetime.now(timezone.utc)
        year_int, month_int = now.year, now.month

    stmt = (
        select(
            cast(Message.created_at, Date).label("date"),
            func.count().label("message_count"),
            func.coalesce(func.sum(Message.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(Message.output_tokens), 0).label("total_output_tokens"),
        )
        .where(
            and_(
                Message.user_id == user_id,
                Message.role == "assistant",
                extract("year", Message.created_at) == year_int,
                extract("month", Message.created_at) == month_int,
            )
        )
        .group_by(cast(Message.created_at, Date))
        .order_by(cast(Message.created_at, Date))
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "date": str(row.date),
            "message_count": row.message_count,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
        }
        for row in rows
    ]


@router.get("/by-range")
async def find_and_group_by_date_range(
    start: str = Query(..., description="ISO date string YYYY-MM-DD"),
    end: str = Query(..., description="ISO date string YYYY-MM-DD"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get usage stats between two dates, grouped by model."""
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    stmt = (
        select(
            Message.model,
            func.count().label("message_count"),
            func.coalesce(func.sum(Message.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(Message.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(Message.token_count), 0).label("total_tokens"),
        )
        .where(
            and_(
                Message.user_id == user_id,
                Message.role == "assistant",
                Message.created_at >= start_dt,
                Message.created_at <= end_dt,
            )
        )
        .group_by(Message.model)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "model": row.model,
            "message_count": row.message_count,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_tokens": row.total_tokens,
        }
        for row in rows
    ]
