"""Agent CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, asc, delete, desc, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent, AgentKnowledgeBase, AgentFile
from app.models.agent_ops import AgentDocument
from app.models.knowledge import KnowledgeBase
from app.models.session import Session
from app.models.message import Message
from app.models.topic import Topic

router = APIRouter(prefix="/api/agents", tags=["Agents"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateAgentBody(BaseModel):
    slug: str
    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None
    chat_config: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None
    plugins: Optional[list[str]] = None
    opening_message: Optional[str] = None
    opening_questions: Optional[list[str]] = None


class UpdateAgentBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None
    chat_config: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None
    plugins: Optional[list[str]] = None
    pinned: Optional[bool] = None
    opening_message: Optional[str] = None
    opening_questions: Optional[list[str]] = None
    session_group_id: Optional[str] = None


class BatchFileIdsBody(BaseModel):
    file_ids: list[str]


class BatchKBIdsBody(BaseModel):
    knowledge_base_ids: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/query")
async def query_agents(
    keywords: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Agent).where(Agent.user_id == user_id)
    if keywords:
        pattern = f"%{keywords}%"
        stmt = stmt.where(Agent.title.ilike(pattern))
    stmt = stmt.order_by(desc(Agent.pinned), desc(Agent.updated_at)).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_agent_dict(r) for r in rows]


@router.get("/check-market")
async def check_by_market_identifier(
    identifier: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = (await session.execute(
        select(Agent).where(
            and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
        )
    )).scalar_one_or_none()
    return {"exists": agent is not None, "agent_id": agent.id if agent else None}


@router.get("/by-market/{identifier}")
async def get_by_market_identifier(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = (await session.execute(
        select(Agent).where(
            and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return _agent_dict(agent)


@router.get("/by-forked-from/{identifier}")
async def get_by_forked_from(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = (await session.execute(
        select(Agent).where(
            and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return _agent_dict(agent)


@router.get("/builtin")
@router.get("/builtin/{slug}")
async def get_builtin_agent(
    slug: str = "default",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get or create a builtin agent by slug (e.g. 'inbox', 'page-copilot').

    Mirrors the TS ``agentModel.getBuiltinAgent`` behaviour:
    1. Find existing agent by slug
    2. If not found, auto-create a virtual agent with the slug
    3. Return the real DB row so the frontend gets a valid UUID ``id``
    """
    # 1. Try existing agent by slug
    agent = await _find_agent_by_slug(session, user_id, slug)
    if agent:
        return _agent_dict(agent)

    # 2. Auto-create the builtin agent
    agent = Agent(
        user_id=user_id,
        slug=slug,
        title="Default Agent" if slug in ("default", "inbox") else slug.replace("-", " ").title(),
        virtual=True,
    )
    session.add(agent)
    await session.flush()
    await session.commit()
    await session.refresh(agent)
    return _agent_dict(agent)


@router.get("/config-by-session/{session_id}")
async def get_agent_config_by_session_id(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get the agent config associated with a session."""
    from app.models.session import Session as SessionModel
    sess = (await session.execute(
        select(SessionModel).where(
            and_(SessionModel.id == session_id, SessionModel.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not sess or not sess.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session or agent not found")
    agent = await _find_agent(session, user_id, sess.agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return {
        "model": agent.model,
        "provider": agent.provider,
        "system_role": agent.system_role,
        "chat_config": agent.chat_config,
        "tts": agent.tts,
        "plugins": agent.plugins,
    }


@router.get("")
async def list_agents(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Agent)
        .where(Agent.user_id == user_id)
        .order_by(desc(Agent.pinned), desc(Agent.updated_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_agent_dict(r) for r in rows]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # First try direct ID lookup
    agent = await _find_agent(session, user_id, agent_id)
    if agent:
        return _agent_dict(agent)

    # Fallback: try slug lookup (e.g. "inbox" is a builtin slug, not a UUID)
    agent = await _find_agent_by_slug(session, user_id, agent_id)
    if agent:
        return _agent_dict(agent)

    # Return null (not 404) to match TRPC behavior — frontend handles null gracefully
    return None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: CreateAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = Agent(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(agent)
    await session.flush()
    return {"id": agent.id}


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    body: UpdateAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Agent)
        .where(and_(Agent.id == agent_id, Agent.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # 1. Find linked session IDs
    linked = await session.execute(
        select(Session.id).where(
            and_(Session.agent_id == agent_id, Session.user_id == user_id)
        )
    )
    session_ids = linked.scalars().all()

    if session_ids:
        # 2. Delete messages, topics for those sessions
        await session.execute(
            delete(Message).where(Message.session_id.in_(session_ids))
        )
        await session.execute(
            delete(Topic).where(Topic.session_id.in_(session_ids))
        )

    # 3. Delete agents_to_sessions junction rows
    await session.execute(
        text("DELETE FROM agents_to_sessions WHERE agent_id = :aid AND user_id = :uid"),
        {"aid": agent_id, "uid": user_id},
    )

    if session_ids:
        # 4. Delete sessions
        await session.execute(
            delete(Session).where(Session.id.in_(session_ids))
        )

    # 5. Delete agent-specific relations
    await session.execute(
        delete(AgentKnowledgeBase).where(
            and_(AgentKnowledgeBase.agent_id == agent_id, AgentKnowledgeBase.user_id == user_id)
        )
    )
    await session.execute(
        delete(AgentFile).where(
            and_(AgentFile.agent_id == agent_id, AgentFile.user_id == user_id)
        )
    )
    await session.execute(
        delete(AgentDocument).where(
            and_(AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id)
        )
    )

    # 6. Delete the agent
    await session.execute(
        delete(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id))
    )
    return {"ok": True}


@router.post("/{agent_id}/duplicate")
async def duplicate_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    orig = await _find_agent(session, user_id, agent_id)
    if not orig:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    import uuid as _uuid
    new_slug = f"{orig.slug}-copy-{_uuid.uuid4().hex[:6]}"
    new_agent = Agent(
        user_id=user_id,
        slug=new_slug,
        title=f"{orig.title or ''} (copy)",
        description=orig.description,
        avatar=orig.avatar,
        system_role=orig.system_role,
        model=orig.model,
        provider=orig.provider,
        tags=orig.tags,
        chat_config=orig.chat_config,
        tts=orig.tts,
        plugins=orig.plugins,
        opening_message=orig.opening_message,
        opening_questions=orig.opening_questions,
        session_group_id=orig.session_group_id,
    )
    session.add(new_agent)
    await session.flush()
    # Copy file links
    file_links = (await session.execute(
        select(AgentFile).where(and_(AgentFile.agent_id == agent_id, AgentFile.user_id == user_id))
    )).scalars().all()
    for fl in file_links:
        session.add(AgentFile(agent_id=new_agent.id, file_id=fl.file_id, user_id=user_id, enabled=fl.enabled))
    # Copy KB links
    kb_links = (await session.execute(
        select(AgentKnowledgeBase).where(and_(AgentKnowledgeBase.agent_id == agent_id, AgentKnowledgeBase.user_id == user_id))
    )).scalars().all()
    for kl in kb_links:
        session.add(AgentKnowledgeBase(agent_id=new_agent.id, knowledge_base_id=kl.knowledge_base_id, user_id=user_id, enabled=kl.enabled))
    await session.flush()
    return {"id": new_agent.id}


@router.get("/{agent_id}/config")
async def get_agent_config(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = await _find_agent(session, user_id, agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return {
        "model": agent.model,
        "provider": agent.provider,
        "system_role": agent.system_role,
        "chat_config": agent.chat_config,
        "tts": agent.tts,
        "plugins": agent.plugins,
    }


@router.put("/{agent_id}/pinned")
async def update_agent_pinned(
    agent_id: str,
    pinned: bool = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Agent)
        .where(and_(Agent.id == agent_id, Agent.user_id == user_id))
        .values(pinned=pinned, updated_at=_now())
    )
    return {"ok": True}


@router.get("/{agent_id}/knowledge-and-files")
async def get_knowledge_bases_and_files(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Get files
    file_links = (await session.execute(
        select(AgentFile).where(and_(AgentFile.agent_id == agent_id, AgentFile.user_id == user_id))
    )).scalars().all()
    # Get KBs
    kb_links = (await session.execute(
        select(AgentKnowledgeBase).where(
            and_(AgentKnowledgeBase.agent_id == agent_id, AgentKnowledgeBase.user_id == user_id)
        )
    )).scalars().all()
    kb_ids = [kl.knowledge_base_id for kl in kb_links]
    kbs = []
    if kb_ids:
        kbs = (await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        )).scalars().all()
    return {
        "files": [{"file_id": f.file_id, "enabled": f.enabled} for f in file_links],
        "knowledge_bases": [
            {"id": kb.id, "name": kb.name, "enabled": next((kl.enabled for kl in kb_links if kl.knowledge_base_id == kb.id), True)}
            for kb in kbs
        ],
    }


# ── Knowledge base links ───────────────────────────────────────

@router.post("/{agent_id}/knowledge-bases/{kb_id}", status_code=status.HTTP_201_CREATED)
async def link_kb(
    agent_id: str,
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    link = AgentKnowledgeBase(agent_id=agent_id, knowledge_base_id=kb_id, user_id=user_id)
    session.add(link)
    await session.flush()
    return {"ok": True}


@router.delete("/{agent_id}/knowledge-bases/{kb_id}")
async def unlink_kb(
    agent_id: str,
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(AgentKnowledgeBase).where(
            and_(
                AgentKnowledgeBase.agent_id == agent_id,
                AgentKnowledgeBase.knowledge_base_id == kb_id,
                AgentKnowledgeBase.user_id == user_id,
            )
        )
    )
    return {"ok": True}


@router.put("/{agent_id}/knowledge-bases/{kb_id}/toggle")
async def toggle_knowledge_base(
    agent_id: str,
    kb_id: str,
    enabled: bool = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(AgentKnowledgeBase)
        .where(and_(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.knowledge_base_id == kb_id,
            AgentKnowledgeBase.user_id == user_id,
        ))
        .values(enabled=enabled)
    )
    return {"ok": True}


@router.post("/{agent_id}/knowledge-bases", status_code=status.HTTP_201_CREATED)
async def create_agent_knowledge_base(
    agent_id: str,
    body: BatchKBIdsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    for kb_id in body.knowledge_base_ids:
        link = AgentKnowledgeBase(agent_id=agent_id, knowledge_base_id=kb_id, user_id=user_id)
        session.add(link)
    await session.flush()
    return {"ok": True}


# ── File links ───────────────────────────────────────────────────

@router.post("/{agent_id}/files", status_code=status.HTTP_201_CREATED)
async def create_agent_files(
    agent_id: str,
    body: BatchFileIdsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    for fid in body.file_ids:
        link = AgentFile(agent_id=agent_id, file_id=fid, user_id=user_id)
        session.add(link)
    await session.flush()
    return {"ok": True}


@router.delete("/{agent_id}/files/{file_id}")
async def delete_agent_file(
    agent_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(AgentFile).where(and_(
            AgentFile.agent_id == agent_id,
            AgentFile.file_id == file_id,
            AgentFile.user_id == user_id,
        ))
    )
    return {"ok": True}


@router.put("/{agent_id}/files/{file_id}/toggle")
async def toggle_file(
    agent_id: str,
    file_id: str,
    enabled: bool = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(AgentFile)
        .where(and_(
            AgentFile.agent_id == agent_id,
            AgentFile.file_id == file_id,
            AgentFile.user_id == user_id,
        ))
        .values(enabled=enabled)
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_agent(session: AsyncSession, user_id: str, agent_id: str) -> Agent | None:
    stmt = select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _find_agent_by_slug(session: AsyncSession, user_id: str, slug: str) -> Agent | None:
    stmt = select(Agent).where(and_(Agent.slug == slug, Agent.user_id == user_id))
    return (await session.execute(stmt)).scalar_one_or_none()


def _agent_dict(a: Agent) -> dict[str, Any]:
    return {
        "id": a.id,
        "slug": a.slug,
        "title": a.title,
        "description": a.description,
        "avatar": a.avatar,
        "system_role": a.system_role,
        "model": a.model,
        "provider": a.provider,
        "tags": a.tags,
        "chat_config": a.chat_config,
        "tts": a.tts,
        "plugins": a.plugins,
        "pinned": a.pinned,
        "opening_message": a.opening_message,
        "opening_questions": a.opening_questions,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
