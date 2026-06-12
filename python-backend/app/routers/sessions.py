"""Session CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.session import Session, SessionGroup
from app.models.topic import Topic
from app.models.message import Message

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSessionBody(BaseModel):
    agent_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    group_id: Optional[str] = None
    session: Optional[dict[str, Any]] = None
    type: str = "agent"


class UpdateSessionBody(BaseModel):
    pinned: Optional[bool] = None
    group_id: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    background_color: Optional[str] = None


class CreateGroupBody(BaseModel):
    name: str
    sort: Optional[int] = None


class UpdateGroupBody(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None


class UpdateSessionConfigBody(BaseModel):
    chat_config: Optional[dict[str, Any]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    system_role: Optional[str] = None


class UpdateGroupOrderBody(BaseModel):
    sort_map: dict[str, int]  # {group_id: sort_order}


class BatchCreateSessionItem(BaseModel):
    id: Optional[str] = None
    type: str = "agent"
    group: Optional[str] = None
    pinned: Optional[bool] = None
    config: Optional[dict[str, Any]] = None
    meta: Optional[dict[str, Any]] = None


class UpdateSessionChatConfigBody(BaseModel):
    chat_config: dict[str, Any]


# ── Session endpoints ────────────────────────────────────────────────

@router.post("/batch")
async def batch_create_sessions(
    body: list[BatchCreateSessionItem],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    added = 0
    for item in body:
        meta = item.meta or {}
        s = Session(
            user_id=user_id,
            type=item.type,
            group_id=item.group,
            pinned=item.pinned or False,
            title=meta.get("title"),
            description=meta.get("description"),
            avatar=meta.get("avatar"),
            background_color=meta.get("backgroundColor") or meta.get("background_color"),
        )
        if item.id:
            s.id = item.id
        session.add(s)
        added += 1
    await session.flush()
    return {"added": added, "ids": [], "skips": [], "success": True}


@router.put("/{session_id}/chat-config")
async def update_session_chat_config(
    session_id: str,
    body: UpdateSessionChatConfigBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    sess = await _find_session(session, user_id, session_id)
    if not sess or not sess.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session or agent not found")
    await session.execute(
        update(Agent)
        .where(and_(Agent.id == sess.agent_id, Agent.user_id == user_id))
        .values(chat_config=body.chat_config, updated_at=_now())
    )
    return {"ok": True}


@router.get("/search")
async def search_sessions(
    keywords: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    pattern = f"%{keywords}%"
    stmt = (
        select(Session)
        .join(Agent, and_(Agent.id == Session.agent_id, Agent.user_id == user_id), isouter=True)
        .where(and_(
            Session.user_id == user_id,
            Agent.title.ilike(pattern),
        ))
        .order_by(desc(Session.updated_at))
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_session_dict(r) for r in rows]


@router.get("/count")
async def count_sessions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    count = (await session.execute(
        select(func.count()).select_from(Session).where(Session.user_id == user_id)
    )).scalar_one()
    return {"count": count}


@router.get("/grouped")
async def get_grouped_sessions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    groups_stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort)
    )
    groups = (await session.execute(groups_stmt)).scalars().all()

    sessions_stmt = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(desc(Session.pinned), desc(Session.updated_at))
    )
    all_sessions = (await session.execute(sessions_stmt)).scalars().all()

    grouped: dict[str, list] = {"default": [], "pinned": []}
    for g in groups:
        grouped[g.id] = []
    for s in all_sessions:
        sd = _session_dict(s)
        if s.pinned:
            grouped["pinned"].append(sd)
        elif s.group_id and s.group_id in grouped:
            grouped[s.group_id].append(sd)
        else:
            grouped["default"].append(sd)
    return {
        "groups": [{"id": g.id, "name": g.name, "sort": g.sort} for g in groups],
        "sessions": grouped,
    }


@router.get("/rank")
async def rank_sessions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Session.id, func.count(Message.id).label("message_count"))
        .outerjoin(Message, and_(Message.session_id == Session.id, Message.user_id == user_id))
        .where(Session.user_id == user_id)
        .group_by(Session.id)
        .order_by(desc("message_count"))
        .limit(20)
    )
    rows = (await session.execute(stmt)).all()
    return [{"session_id": r.id, "message_count": r.message_count} for r in rows]


@router.get("")
async def list_sessions(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(desc(Session.pinned), desc(Session.updated_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_session_dict(r) for r in rows]


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_session(session, user_id, session_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return _session_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    session_payload = body.session or {}
    group_id = body.group_id or session_payload.get("group_id") or session_payload.get("groupId")
    agent_id = body.agent_id

    if body.config and not agent_id and body.type == "agent":
        import uuid as _uuid

        agent_values = _agent_values_from_config(body.config)
        agent_values.setdefault("slug", f"agent-{_uuid.uuid4().hex[:8]}")
        agent = Agent(user_id=user_id, **agent_values)
        session.add(agent)
        await session.flush()
        agent_id = agent.id

    meta = session_payload.get("meta") or {}
    s = Session(
        user_id=user_id,
        agent_id=agent_id,
        group_id=group_id,
        type=body.type,
        title=session_payload.get("title") or meta.get("title"),
        description=session_payload.get("description") or meta.get("description"),
        avatar=session_payload.get("avatar") or meta.get("avatar"),
        background_color=(
            session_payload.get("background_color")
            or session_payload.get("backgroundColor")
            or meta.get("background_color")
            or meta.get("backgroundColor")
        ),
    )
    session.add(s)
    await session.flush()
    return {"id": s.id}


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    body: UpdateSessionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Session)
        .where(and_(Session.id == session_id, Session.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
    )
    return {"ok": True}


@router.post("/remove-all")
async def remove_all_sessions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(delete(Session).where(Session.user_id == user_id))
    return {"ok": True}


@router.post("/{session_id}/clone")
async def clone_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    orig = await _find_session(session, user_id, session_id)
    if not orig:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    new_session = Session(
        user_id=user_id,
        agent_id=orig.agent_id,
        group_id=orig.group_id,
        type=orig.type,
        title=orig.title,
        description=orig.description,
        avatar=orig.avatar,
        background_color=orig.background_color,
    )
    session.add(new_session)
    await session.flush()
    # Clone topics and their messages
    topic_stmt = select(Topic).where(
        and_(Topic.session_id == session_id, Topic.user_id == user_id)
    )
    topics = (await session.execute(topic_stmt)).scalars().all()
    for t in topics:
        new_topic = Topic(
            user_id=user_id,
            title=t.title,
            session_id=new_session.id,
            agent_id=t.agent_id,
        )
        session.add(new_topic)
        await session.flush()
        msg_stmt = select(Message).where(
            and_(Message.topic_id == t.id, Message.user_id == user_id)
        ).order_by(Message.created_at)
        msgs = (await session.execute(msg_stmt)).scalars().all()
        for m in msgs:
            new_msg = Message(
                user_id=user_id,
                role=m.role,
                content=m.content,
                model=m.model,
                provider=m.provider,
                session_id=new_session.id,
                topic_id=new_topic.id,
                agent_id=m.agent_id,
            )
            session.add(new_msg)
    await session.flush()
    return {"id": new_session.id}


@router.put("/{session_id}/config")
async def update_session_config(
    session_id: str,
    body: UpdateSessionConfigBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Update the associated agent's config
    sess = await _find_session(session, user_id, session_id)
    if not sess or not sess.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session or agent not found")
    values = body.model_dump(exclude_none=True)
    if values:
        values["updated_at"] = _now()
        await session.execute(
            update(Agent)
            .where(and_(Agent.id == sess.agent_id, Agent.user_id == user_id))
            .values(**values)
        )
    return {"ok": True}


# ── Session Group endpoints ──────────────────────────────────────────

@router.get("/groups/all")
async def list_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort, SessionGroup.created_at)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": r.id, "name": r.name, "sort": r.sort} for r in rows]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    body: CreateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    g = SessionGroup(user_id=user_id, name=body.name, sort=body.sort)
    session.add(g)
    await session.flush()
    return {"id": g.id}


@router.put("/groups/{group_id}")
async def update_group(
    group_id: str,
    body: UpdateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(SessionGroup)
        .where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Unlink sessions from this group
    await session.execute(
        update(Session)
        .where(and_(Session.group_id == group_id, Session.user_id == user_id))
        .values(group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(
            and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id)
        )
    )
    return {"ok": True}


@router.get("/groups/{group_id}")
async def get_group(
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
    return {"id": grp.id, "name": grp.name, "sort": grp.sort}


@router.post("/groups/remove-all")
async def remove_all_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Session).where(Session.user_id == user_id).values(group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(SessionGroup.user_id == user_id)
    )
    return {"ok": True}


@router.put("/groups/order")
async def update_group_order(
    body: UpdateGroupOrderBody,
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


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_session(db: AsyncSession, user_id: str, session_id: str) -> Session | None:
    stmt = select(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _session_dict(s: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "agent_id": s.agent_id,
        "group_id": s.group_id,
        "type": s.type,
        "pinned": s.pinned,
        "slug": s.slug,
        "title": s.title,
        "description": s.description,
        "avatar": s.avatar,
        "background_color": s.background_color,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _agent_values_from_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "avatar": config.get("avatar"),
        "background_color": config.get("backgroundColor") or config.get("background_color"),
        "chat_config": config.get("chatConfig") or config.get("chat_config"),
        "description": config.get("description"),
        "market_identifier": config.get("marketIdentifier") or config.get("market_identifier"),
        "model": config.get("model") if isinstance(config.get("model"), str) else None,
        "opening_message": config.get("openingMessage") or config.get("opening_message"),
        "opening_questions": config.get("openingQuestions") or config.get("opening_questions"),
        "plugins": config.get("plugins"),
        "provider": config.get("provider"),
        "system_role": config.get("systemRole") or config.get("system_role"),
        "tags": config.get("tags"),
        "title": config.get("title"),
        "tts": config.get("tts"),
    }
