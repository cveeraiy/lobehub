"""Brief Service — standalone brief CRUD, resolve, dismiss.

Ports TS ``brief/index.ts``:
- List briefs with agent avatar enrichment
- List unresolved briefs
- Resolve briefs (approve/feedback/retry/acknowledge)
- Terminal accept rule: approve on result brief completes the task
- Scheduled tasks are exempt from terminal completion
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Brief, Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AgentAvatarInfo:
    """Minimal agent info for brief enrichment."""
    __slots__ = ("id", "title", "avatar", "background_color")

    def __init__(
        self,
        id: str,
        title: Optional[str] = None,
        avatar: Optional[str] = None,
        background_color: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.avatar = avatar
        self.background_color = background_color

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "avatar": self.avatar,
            "backgroundColor": self.background_color,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BriefService:
    """Service for brief CRUD and lifecycle operations."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    # ── Read ──────────────────────────────────────────────────────────

    async def list_briefs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        brief_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """List briefs with pagination."""
        base = select(Brief).where(Brief.user_id == self._uid)
        if brief_type:
            base = base.where(Brief.type == brief_type)

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._db.execute(count_stmt)).scalar_one()

        # Fetch
        stmt = base.order_by(Brief.created_at.desc()).offset(offset).limit(min(limit, 200))
        briefs = (await self._db.execute(stmt)).scalars().all()

        return {"briefs": list(briefs), "total": total}

    async def list_unresolved(self) -> Sequence[Brief]:
        """List all unresolved briefs for the user."""
        stmt = (
            select(Brief)
            .where(
                Brief.user_id == self._uid,
                Brief.resolved_at.is_(None),
            )
            .order_by(Brief.created_at.desc())
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def find_by_id(self, brief_id: str) -> Optional[Brief]:
        """Find a single brief by ID."""
        stmt = select(Brief).where(Brief.id == brief_id, Brief.user_id == self._uid)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def find_by_task_id(self, task_id: str) -> Sequence[Brief]:
        """Find all briefs for a given task."""
        stmt = (
            select(Brief)
            .where(Brief.task_id == task_id, Brief.user_id == self._uid)
            .order_by(Brief.created_at.desc())
        )
        return (await self._db.execute(stmt)).scalars().all()

    # ── Create ────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        brief_type: str,
        title: str,
        summary: str,
        task_id: Optional[str] = None,
        cron_job_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        priority: str = "info",
        actions: Optional[dict[str, Any]] = None,
        trigger: Optional[str] = None,
    ) -> Brief:
        """Create a new brief."""
        brief = Brief(
            user_id=self._uid,
            task_id=task_id,
            cron_job_id=cron_job_id,
            topic_id=topic_id,
            agent_id=agent_id,
            type=brief_type,
            title=title,
            summary=summary,
            priority=priority,
            actions=actions,
            trigger=trigger,
        )
        self._db.add(brief)
        await self._db.flush()
        await self._db.refresh(brief)
        return brief

    # ── Resolve ───────────────────────────────────────────────────────

    async def resolve(
        self,
        brief_id: str,
        *,
        action: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Optional[Brief]:
        """Resolve a brief and propagate accept signals to task lifecycle.

        Terminal accept rule: ``approve`` on a ``result`` brief completes
        the task. ``decision`` briefs are non-terminal checkpoints.

        Tasks parked at ``status == 'scheduled'`` are exempt — they are
        between automated runs and approval is just a UI dismissal.
        """
        brief = await self.find_by_id(brief_id)
        if brief is None:
            return None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            update(Brief)
            .where(Brief.id == brief_id, Brief.user_id == self._uid)
            .values(
                resolved_action=action,
                resolved_comment=comment,
                resolved_at=now,
            )
        )
        await self._db.execute(stmt)
        await self._db.refresh(brief)

        # Terminal accept: approve on result brief → complete the task
        if action == "approve" and brief.task_id and brief.type == "result":
            task_stmt = select(Task).where(
                Task.id == brief.task_id,
                Task.created_by_user_id == self._uid,
            )
            task = (await self._db.execute(task_stmt)).scalar_one_or_none()
            if task and task.status != "scheduled":
                await self._db.execute(
                    update(Task)
                    .where(Task.id == brief.task_id)
                    .values(status="completed", error=None, completed_at=now)
                )

        return brief

    # ── Mark read ─────────────────────────────────────────────────────

    async def mark_read(self, brief_id: str) -> bool:
        """Mark a brief as read. Returns False if not found."""
        result = await self._db.execute(
            update(Brief)
            .where(Brief.id == brief_id, Brief.user_id == self._uid)
            .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        return result.rowcount > 0  # type: ignore[union-attr]

    # ── Delete ────────────────────────────────────────────────────────

    async def delete(self, brief_id: str) -> bool:
        """Delete a brief by ID. Returns False if not found."""
        from sqlalchemy import delete as sa_delete
        result = await self._db.execute(
            sa_delete(Brief).where(Brief.id == brief_id, Brief.user_id == self._uid)
        )
        return result.rowcount > 0  # type: ignore[union-attr]
