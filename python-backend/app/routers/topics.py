"""Topic CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.models.topic import Topic
from app.models.topic_ext import TopicShare

router = APIRouter(prefix="/api/topics", tags=["Topics"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _delete_topics_by_ids(
    session: AsyncSession,
    user_id: str,
    topic_ids: list[str],
) -> None:
    if not topic_ids:
        return

    await session.execute(
        text("DELETE FROM agent_eval_run_topics WHERE topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids},
    )
    await session.execute(
        text("DELETE FROM task_topics WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text(
            "UPDATE tasks SET current_topic_id = NULL "
            "WHERE created_by_user_id = :uid AND current_topic_id = ANY(:topic_ids)"
        ),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text(
            "UPDATE task_comments SET topic_id = NULL "
            "WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"
        ),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM topic_documents WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM topic_shares WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text(
            "UPDATE threads SET parent_thread_id = NULL, source_message_id = NULL "
            "WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"
        ),
        {"topic_ids": topic_ids, "uid": user_id},
    )

    message_ids = (
        await session.execute(
            select(Message.id).where(
                and_(Message.user_id == user_id, Message.topic_id.in_(topic_ids))
            )
        )
    ).scalars().all()

    if message_ids:
        query_ids = (
            await session.execute(
                text(
                    "SELECT id FROM message_queries "
                    "WHERE user_id = :uid AND message_id = ANY(:message_ids)"
                ),
                {"message_ids": message_ids, "uid": user_id},
            )
        ).scalars().all()
        if query_ids:
            await session.execute(
                text(
                    "DELETE FROM message_query_chunks "
                    "WHERE user_id = :uid AND query_id = ANY(:query_ids)"
                ),
                {"query_ids": query_ids, "uid": user_id},
            )

        await session.execute(
            text("DELETE FROM message_queries WHERE user_id = :uid AND message_id = ANY(:message_ids)"),
            {"message_ids": message_ids, "uid": user_id},
        )
        await session.execute(
            text("DELETE FROM messages_files WHERE user_id = :uid AND message_id = ANY(:message_ids)"),
            {"message_ids": message_ids, "uid": user_id},
        )
        await session.execute(
            text("DELETE FROM message_chunks WHERE user_id = :uid AND message_id = ANY(:message_ids)"),
            {"message_ids": message_ids, "uid": user_id},
        )
        await session.execute(
            text("DELETE FROM message_plugins WHERE message_id = ANY(:message_ids)"),
            {"message_ids": message_ids},
        )
        await session.execute(
            text("DELETE FROM message_tts WHERE message_id = ANY(:message_ids)"),
            {"message_ids": message_ids},
        )
        await session.execute(
            text("DELETE FROM message_translates WHERE message_id = ANY(:message_ids)"),
            {"message_ids": message_ids},
        )
        await session.execute(
            text(
                "UPDATE message_groups SET parent_message_id = NULL "
                "WHERE user_id = :uid AND parent_message_id = ANY(:message_ids)"
            ),
            {"message_ids": message_ids, "uid": user_id},
        )
        await session.execute(
            text(
                "UPDATE messages SET parent_id = NULL "
                "WHERE user_id = :uid AND parent_id = ANY(:message_ids)"
            ),
            {"message_ids": message_ids, "uid": user_id},
        )
        await session.execute(delete(Message).where(Message.id.in_(message_ids)))

    await session.execute(
        text("DELETE FROM message_groups WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM threads WHERE user_id = :uid AND topic_id = ANY(:topic_ids)"),
        {"topic_ids": topic_ids, "uid": user_id},
    )
    await session.execute(delete(Topic).where(and_(Topic.id.in_(topic_ids), Topic.user_id == user_id)))


# ── Schemas ──────────────────────────────────────────────────────────

class CreateTopicBody(BaseModel):
    title: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    favorite: bool = False


class UpdateTopicBody(BaseModel):
    title: Optional[str] = None
    favorite: Optional[bool] = None
    status: Optional[str] = None
    history_summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class BatchCreateTopicsBody(BaseModel):
    topics: list[CreateTopicBody]


class ImportTopicBody(BaseModel):
    title: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    favorite: bool = False
    messages: Optional[list[dict[str, Any]]] = None


class EnableSharingBody(BaseModel):
    topic_id: str
    is_public: bool = True


class UpdateShareVisibilityBody(BaseModel):
    is_public: bool


class BatchDeleteBody(BaseModel):
    ids: list[str]


class ShareBody(BaseModel):
    visibility: Optional[str] = None


class CloneTopicBody(BaseModel):
    new_title: Optional[str] = None


# ── Frontend path aliases (must come before dynamic routes) ──────────

@router.post("/batch-delete")
async def batch_delete_topics(
    body: BatchDeleteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /batch-delete — frontend path."""
    if body.ids:
        topic_ids = (
            await session.execute(
                select(Topic.id).where(and_(Topic.id.in_(body.ids), Topic.user_id == user_id))
            )
        ).scalars().all()
        await _delete_topics_by_ids(session, user_id, topic_ids)
    return {"ok": True}


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/search")
async def search_topics(
    keywords: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    pattern = f"%{keywords}%"
    stmt = (
        select(Topic)
        .where(and_(Topic.user_id == user_id, Topic.title.ilike(pattern)))
        .order_by(desc(Topic.updated_at))
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(r) for r in rows]


@router.get("/count")
async def count_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(func.count()).select_from(Topic).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    count = (await session.execute(stmt)).scalar_one()
    return {"count": count}


@router.get("/has-topics")
async def has_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(func.count()).select_from(Topic).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    count = (await session.execute(stmt)).scalar_one()
    return {"has_topics": count > 0}


@router.get("/recent")
async def recent_topics(
    limit: int = 10,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Topic)
        .where(Topic.user_id == user_id)
        .order_by(desc(Topic.updated_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(r) for r in rows]


@router.get("/rank")
async def rank_topics(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Topic.id, Topic.title, func.count(Message.id).label("message_count"))
        .outerjoin(Message, and_(Message.topic_id == Topic.id, Message.user_id == user_id))
        .where(Topic.user_id == user_id)
        .group_by(Topic.id)
        .order_by(desc("message_count"))
        .limit(20)
    )
    rows = (await session.execute(stmt)).all()
    return [{"id": r.id, "title": r.title, "message_count": r.message_count} for r in rows]


@router.get("/all")
async def get_all_topics(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Topic)
        .where(Topic.user_id == user_id)
        .order_by(desc(Topic.updated_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(r) for r in rows]


@router.get("/cron-grouped")
async def get_cron_topics_grouped(
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Topic)
        .where(
            and_(
                Topic.user_id == user_id,
                Topic.trigger == "cron",
                Topic.metadata_.is_not(None),
            )
        )
        .order_by(desc(Topic.updated_at))
    )
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)

    topics = (await session.execute(stmt)).scalars().all()

    result: dict[str, list[dict[str, Any]]] = {}
    for t in topics:
        metadata = t.metadata_ or {}
        cron_job_id = metadata.get("cronJobId") or metadata.get("cron_job_id")
        if not cron_job_id:
            continue

        result.setdefault(cron_job_id, []).append(_topic_dict(t))

    return [{"cronJobId": cron_job_id, "topics": items} for cron_job_id, items in result.items()]


@router.get("")
async def list_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Topic).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    stmt = stmt.order_by(desc(Topic.favorite), desc(Topic.updated_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(r) for r in rows]


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_topic(session, user_id, topic_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return _topic_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: CreateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    t = Topic(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(t)
    await session.flush()
    return {"id": t.id}


@router.put("/{topic_id}")
async def update_topic(
    topic_id: str,
    body: UpdateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is not None:
            if k == "metadata":
                values["metadata_"] = v
            else:
                values[k] = v
    values["updated_at"] = _now()
    stmt = (
        update(Topic)
        .where(and_(Topic.id == topic_id, Topic.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    topic_ids = (
        await session.execute(
            select(Topic.id).where(and_(Topic.id == topic_id, Topic.user_id == user_id))
        )
    ).scalars().all()
    await _delete_topics_by_ids(session, user_id, topic_ids)
    return {"ok": True}


@router.delete("")
async def batch_delete_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all topics matching filters."""
    stmt = select(Topic.id).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    topic_ids = (await session.execute(stmt)).scalars().all()
    await _delete_topics_by_ids(session, user_id, topic_ids)
    return {"ok": True}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_topics(
    body: BatchCreateTopicsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    ids = []
    for item in body.topics:
        t = Topic(user_id=user_id, **item.model_dump(exclude_none=True))
        session.add(t)
        ids.append(t)
    await session.flush()
    return {"ids": [t.id for t in ids]}


@router.post("/batch-delete-by-agent")
async def batch_delete_by_agent(
    agent_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    topic_ids = (
        await session.execute(
            select(Topic.id).where(and_(Topic.agent_id == agent_id, Topic.user_id == user_id))
        )
    ).scalars().all()
    await _delete_topics_by_ids(session, user_id, topic_ids)
    return {"ok": True}


@router.post("/batch-delete-by-session")
async def batch_delete_by_session(
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    topic_ids = (
        await session.execute(
            select(Topic.id).where(and_(Topic.session_id == session_id, Topic.user_id == user_id))
        )
    ).scalars().all()
    await _delete_topics_by_ids(session, user_id, topic_ids)
    return {"ok": True}


@router.post("/{topic_id}/clone")
async def clone_topic(
    topic_id: str,
    body: Optional[CloneTopicBody] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    orig = await _find_topic(session, user_id, topic_id)
    if not orig:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    new_topic = Topic(
        user_id=user_id,
        title=body.new_title if body and body.new_title else f"{orig.title or ''} (copy)",
        session_id=orig.session_id,
        agent_id=orig.agent_id,
        favorite=orig.favorite,
        metadata_=orig.metadata_,
    )
    session.add(new_topic)
    await session.flush()
    # Clone messages
    msg_stmt = select(Message).where(
        and_(Message.topic_id == topic_id, Message.user_id == user_id)
    ).order_by(Message.created_at)
    msgs = (await session.execute(msg_stmt)).scalars().all()
    for m in msgs:
        new_msg = Message(
            user_id=user_id,
            role=m.role,
            content=m.content,
            model=m.model,
            provider=m.provider,
            session_id=m.session_id,
            topic_id=new_topic.id,
            agent_id=m.agent_id,
        )
        session.add(new_msg)
    await session.flush()
    return {"id": new_topic.id}


@router.get("/{topic_id}/context")
async def get_topic_context(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    topic = await _find_topic(session, user_id, topic_id)
    if not topic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    msg_count = (await session.execute(
        select(func.count()).select_from(Message).where(
            and_(Message.topic_id == topic_id, Message.user_id == user_id)
        )
    )).scalar_one()
    return {
        "topic": _topic_dict(topic),
        "message_count": msg_count,
    }


@router.post("/import")
async def import_topic(
    body: ImportTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    t = Topic(
        user_id=user_id,
        title=body.title,
        session_id=body.session_id,
        agent_id=body.agent_id,
        favorite=body.favorite,
    )
    session.add(t)
    await session.flush()
    if body.messages:
        for msg_data in body.messages:
            msg = Message(
                user_id=user_id,
                topic_id=t.id,
                role=msg_data.get("role", "user"),
                content=msg_data.get("content"),
                model=msg_data.get("model"),
                provider=msg_data.get("provider"),
            )
            session.add(msg)
        await session.flush()
    return {"id": t.id}


# ── Sharing (frontend path aliases) ──────────────────────────────────

@router.post("/{topic_id}/share")
async def share_topic_alias(
    topic_id: str,
    body: ShareBody = ShareBody(),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /{topic_id}/share — frontend path (enable sharing)."""
    return await enable_sharing(topic_id, user_id=user_id, session=session)


@router.put("/{topic_id}/share")
async def update_share_alias(
    topic_id: str,
    body: ShareBody = ShareBody(),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: PUT /{topic_id}/share — frontend path (update visibility)."""
    vis_body = UpdateShareVisibilityBody(is_public=body.visibility == "public" if body.visibility else True)
    return await update_share_visibility(topic_id, vis_body, user_id=user_id, session=session)


@router.delete("/{topic_id}/share")
async def delete_share_alias(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: DELETE /{topic_id}/share — frontend path (disable sharing)."""
    return await disable_sharing(topic_id, user_id=user_id, session=session)


# ── Sharing (canonical) ──────────────────────────────────────────────

@router.post("/{topic_id}/share/enable")
async def enable_sharing(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    existing = (await session.execute(
        select(TopicShare).where(
            and_(TopicShare.topic_id == topic_id, TopicShare.user_id == user_id)
        )
    )).scalar_one_or_none()
    if existing:
        return {"share_id": existing.id}
    share = TopicShare(topic_id=topic_id, user_id=user_id, is_public=True)
    session.add(share)
    await session.flush()
    return {"share_id": share.id}


@router.post("/{topic_id}/share/disable")
async def disable_sharing(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(TopicShare).where(
            and_(TopicShare.topic_id == topic_id, TopicShare.user_id == user_id)
        )
    )
    return {"ok": True}


@router.get("/{topic_id}/share")
async def get_share_info(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    share = (await session.execute(
        select(TopicShare).where(
            and_(TopicShare.topic_id == topic_id, TopicShare.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not share:
        return None
    return {
        "share_id": share.id,
        "is_public": share.is_public,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


@router.put("/{topic_id}/share/visibility")
async def update_share_visibility(
    topic_id: str,
    body: UpdateShareVisibilityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(TopicShare)
        .where(and_(TopicShare.topic_id == topic_id, TopicShare.user_id == user_id))
        .values(is_public=body.is_public, updated_at=_now())
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_topic(db: AsyncSession, user_id: str, topic_id: str) -> Topic | None:
    stmt = select(Topic).where(and_(Topic.id == topic_id, Topic.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _topic_dict(t: Topic) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "session_id": t.session_id,
        "agent_id": t.agent_id,
        "favorite": t.favorite,
        "status": t.status,
        "metadata": t.metadata_,
        "history_summary": t.history_summary,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
