"""Chat Groups router — multi-agent collaboration groups (TS agentGroup equivalent).

Operates on chat_groups + chat_groups_agents tables for multi-agent group chat.
This is distinct from agent_groups.py which handles folder-like session grouping.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.chat_group import ChatGroup, ChatGroupAgent

router = APIRouter(prefix="/api/chat-groups", tags=["Chat Groups"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateChatGroupBody(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    background_color: Optional[str] = None
    backgroundColor: Optional[str] = None
    market_identifier: Optional[str] = None
    marketIdentifier: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = None
    editorData: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    client_id: Optional[str] = None
    clientId: Optional[str] = None
    group_id: Optional[str] = None
    groupId: Optional[str] = None
    pinned: Optional[bool] = None


class UpdateChatGroupBody(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    background_color: Optional[str] = None
    backgroundColor: Optional[str] = None
    market_identifier: Optional[str] = None
    marketIdentifier: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = None
    editorData: Optional[dict[str, Any]] = None
    config: Optional[dict[str, Any]] = None
    client_id: Optional[str] = None
    clientId: Optional[str] = None
    group_id: Optional[str] = None
    groupId: Optional[str] = None
    pinned: Optional[bool] = None


class CreateGroupWithMembersBody(BaseModel):
    group_config: CreateChatGroupBody
    members: list[dict[str, Any]] = []
    supervisor_config: Optional[dict[str, Any]] = None


class AddAgentsBody(BaseModel):
    agent_ids: list[str]


class RemoveAgentsBody(BaseModel):
    agent_ids: list[str]
    delete_virtual_agents: bool = True


class BatchCreateAgentsBody(BaseModel):
    agents: list[dict[str, Any]]
    group_id: Optional[str] = None


class UpdateAgentInGroupBody(BaseModel):
    enabled: Optional[bool] = None
    order: Optional[int] = None
    role: Optional[str] = None


class DuplicateGroupBody(BaseModel):
    new_title: Optional[str] = None


class CheckRemovalBody(BaseModel):
    agent_ids: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_chat_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ChatGroup)
        .where(ChatGroup.user_id == user_id)
        .order_by(desc(ChatGroup.updated_at))
    )
    groups = (await session.execute(stmt)).scalars().all()
    result = []
    for g in groups:
        agents = await _get_group_agents(session, user_id, g.id)
        result.append({**_group_dict(g), "agents": agents})
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat_group(
    body: CreateChatGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    group = ChatGroup(
        user_id=user_id,
        **_group_values(body),
    )
    session.add(group)
    await session.flush()

    # Create a supervisor agent (virtual)
    supervisor = Agent(
        user_id=user_id,
        slug=f"supervisor-{group.id[:8]}",
        title=body.title or body.name or "Supervisor",
        virtual=True,
    )
    session.add(supervisor)
    await session.flush()

    # Link supervisor to group
    link = ChatGroupAgent(
        chat_group_id=group.id,
        group_id=group.id,
        agent_id=supervisor.id,
        user_id=user_id,
        role="supervisor",
        order=-1,
    )
    session.add(link)
    await session.flush()

    return {"group": _group_dict(group), "supervisor_agent_id": supervisor.id}


@router.post("/with-members", status_code=status.HTTP_201_CREATED)
async def create_group_with_members(
    body: CreateGroupWithMembersBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # 1. Create virtual member agents
    member_ids = []
    for member in body.members:
        agent = Agent(
            user_id=user_id,
            slug=member.get("slug") or f"member-{_uuid.uuid4().hex[:8]}",
            title=member.get("title"),
            description=member.get("description"),
            avatar=member.get("avatar"),
            model=member.get("model"),
            provider=member.get("provider"),
            system_role=member.get("systemRole") or member.get("system_role"),
            virtual=True,
        )
        session.add(agent)
        await session.flush()
        member_ids.append(agent.id)

    # 2. Create supervisor
    sup_cfg = body.supervisor_config or {}
    supervisor = Agent(
        user_id=user_id,
        slug=f"supervisor-{_uuid.uuid4().hex[:8]}",
        title=sup_cfg.get("title") or body.group_config.title or body.group_config.name or "Supervisor",
        model=sup_cfg.get("model"),
        provider=sup_cfg.get("provider"),
        system_role=sup_cfg.get("systemRole") or sup_cfg.get("system_role"),
        virtual=True,
    )
    session.add(supervisor)
    await session.flush()

    # 3. Create group
    group = ChatGroup(
        user_id=user_id,
        **_group_values(body.group_config),
    )
    session.add(group)
    await session.flush()

    # 4. Link supervisor
    session.add(ChatGroupAgent(
        chat_group_id=group.id,
        group_id=group.id,
        agent_id=supervisor.id,
        user_id=user_id,
        role="supervisor",
        order=-1,
    ))

    # 5. Link members
    for index, mid in enumerate(member_ids):
        session.add(ChatGroupAgent(
            chat_group_id=group.id,
            group_id=group.id,
            agent_id=mid,
            user_id=user_id,
            role="participant",
            order=index,
        ))

    await session.flush()
    return {
        "group_id": group.id,
        "supervisor_agent_id": supervisor.id,
        "agent_ids": member_ids,
    }


@router.get("/by-forked-from/{identifier}")
async def get_group_by_forked_from_identifier(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ChatGroup.id)
        .where(
            and_(
                ChatGroup.user_id == user_id,
                ChatGroup.config["forkedFromIdentifier"].as_string() == identifier,
            )
        )
        .order_by(desc(ChatGroup.updated_at))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@router.get("/{group_id}")
async def get_chat_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    grp = await _find_group(session, user_id, group_id)
    if not grp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat group not found")
    return _group_dict(grp)


@router.get("/{group_id}/detail")
async def get_chat_group_detail(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    grp = await _find_group(session, user_id, group_id)
    if not grp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat group not found")
    agents = await _get_group_agents(session, user_id, group_id)
    return {**_group_dict(grp), "agents": agents}


@router.put("/{group_id}")
async def update_chat_group(
    group_id: str,
    body: UpdateChatGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = _group_values(body)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(ChatGroup)
        .where(and_(ChatGroup.id == group_id, ChatGroup.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/{group_id}")
async def delete_chat_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Get virtual agents in this group for cleanup
    virtual_agent_ids = (await session.execute(
        select(ChatGroupAgent.agent_id)
        .join(Agent, Agent.id == ChatGroupAgent.agent_id)
        .where(
            and_(
                ChatGroupAgent.chat_group_id == group_id,
                ChatGroupAgent.user_id == user_id,
                Agent.virtual == True,
            )
        )
    )).scalars().all()

    # Delete links
    await session.execute(
        delete(ChatGroupAgent).where(
            and_(ChatGroupAgent.chat_group_id == group_id, ChatGroupAgent.user_id == user_id)
        )
    )

    # Delete virtual agents
    if virtual_agent_ids:
        await session.execute(
            delete(Agent).where(Agent.id.in_(virtual_agent_ids))
        )

    # Delete group
    await session.execute(
        delete(ChatGroup).where(and_(ChatGroup.id == group_id, ChatGroup.user_id == user_id))
    )
    return {"ok": True}


@router.post("/{group_id}/duplicate")
async def duplicate_chat_group(
    group_id: str,
    body: DuplicateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    grp = await _find_group(session, user_id, group_id)
    if not grp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat group not found")

    new_group = ChatGroup(
        user_id=user_id,
        title=body.new_title or f"{grp.title or ''} (copy)",
        description=grp.description,
        avatar=grp.avatar,
        background_color=grp.background_color,
        config=grp.config,
        content=grp.content,
        editor_data=grp.editor_data,
        pinned=grp.pinned,
    )
    session.add(new_group)
    await session.flush()

    # Get existing members
    members = (await session.execute(
        select(ChatGroupAgent, Agent)
        .join(Agent, Agent.id == ChatGroupAgent.agent_id)
        .where(and_(ChatGroupAgent.chat_group_id == group_id, ChatGroupAgent.user_id == user_id))
        .order_by(ChatGroupAgent.order)
    )).all()

    new_supervisor_id: str | None = None
    for cga, agent in members:
        if agent.virtual:
            # Copy virtual agents
            new_agent = Agent(
                user_id=user_id,
                slug=f"{agent.slug or 'agent'}-copy-{_uuid.uuid4().hex[:6]}",
                title=agent.title,
                description=agent.description,
                avatar=agent.avatar,
                system_role=agent.system_role,
                model=agent.model,
                provider=agent.provider,
                virtual=True,
            )
            session.add(new_agent)
            await session.flush()
            session.add(ChatGroupAgent(
                chat_group_id=new_group.id,
                group_id=new_group.id,
                agent_id=new_agent.id,
                user_id=user_id,
                role=cga.role,
                order=cga.order,
                enabled=cga.enabled,
            ))
            if cga.role == "supervisor":
                new_supervisor_id = new_agent.id
        else:
            # Reference non-virtual agents
            session.add(ChatGroupAgent(
                chat_group_id=new_group.id,
                group_id=new_group.id,
                agent_id=agent.id,
                user_id=user_id,
                role=cga.role,
                order=cga.order,
                enabled=cga.enabled,
            ))

    await session.flush()
    return {"id": new_group.id, "group_id": new_group.id, "supervisor_agent_id": new_supervisor_id}


@router.get("/{group_id}/agents")
async def get_group_agents(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await _get_group_agents(session, user_id, group_id)


@router.post("/{group_id}/agents")
async def add_agents_to_group(
    group_id: str,
    body: AddAgentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    added = []
    existing_ids = []
    for agent_id in body.agent_ids:
        # Check if already linked
        existing = (await session.execute(
            select(ChatGroupAgent).where(
                and_(
                    ChatGroupAgent.chat_group_id == group_id,
                    ChatGroupAgent.agent_id == agent_id,
                )
            )
        )).scalar_one_or_none()
        if not existing:
            session.add(ChatGroupAgent(
                chat_group_id=group_id,
                group_id=group_id,
                agent_id=agent_id,
                user_id=user_id,
                role="participant",
            ))
            added.append({
                "agent_id": agent_id,
                "chat_group_id": group_id,
                "role": "participant",
                "user_id": user_id,
            })
        else:
            existing_ids.append(agent_id)
    await session.flush()
    return {"added": added, "existing": existing_ids}


@router.post("/{group_id}/agents/batch-create")
async def batch_create_agents_in_group(
    group_id: str,
    body: BatchCreateAgentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent_ids = []
    created_agents = []
    for index, agent_cfg in enumerate(body.agents):
        agent = Agent(
            user_id=user_id,
            slug=agent_cfg.get("slug") or f"agent-{_uuid.uuid4().hex[:8]}",
            title=agent_cfg.get("title"),
            description=agent_cfg.get("description"),
            avatar=agent_cfg.get("avatar"),
            model=agent_cfg.get("model"),
            provider=agent_cfg.get("provider"),
            system_role=agent_cfg.get("systemRole") or agent_cfg.get("system_role"),
            virtual=True,
        )
        session.add(agent)
        await session.flush()
        agent_ids.append(agent.id)
        created_agents.append({"id": agent.id, "title": agent.title})

        session.add(ChatGroupAgent(
            chat_group_id=group_id,
            group_id=group_id,
            agent_id=agent.id,
            user_id=user_id,
            role="participant",
            order=index,
        ))

    await session.flush()
    return {"agent_ids": agent_ids, "agents": created_agents}


@router.post("/{group_id}/agents/remove")
async def remove_agents_from_group(
    group_id: str,
    body: RemoveAgentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    virtual_ids = []
    if body.delete_virtual_agents:
        virtual_ids = (await session.execute(
            select(Agent.id).where(
                and_(
                    Agent.id.in_(body.agent_ids),
                    Agent.user_id == user_id,
                    Agent.virtual == True,
                )
            )
        )).scalars().all()

    # Remove links
    await session.execute(
        delete(ChatGroupAgent).where(
            and_(
                ChatGroupAgent.chat_group_id == group_id,
                ChatGroupAgent.agent_id.in_(body.agent_ids),
            )
        )
    )

    # Delete virtual agents
    if virtual_ids:
        await session.execute(
            delete(Agent).where(Agent.id.in_(virtual_ids))
        )

    return {"ok": True, "deleted_virtual_agents": list(virtual_ids)}


@router.put("/{group_id}/agents/{agent_id}")
async def update_agent_in_group(
    group_id: str,
    agent_id: str,
    body: UpdateAgentInGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {}
    if body.enabled is not None:
        values["enabled"] = body.enabled
    if body.order is not None:
        values["order"] = body.order
    if body.role is not None:
        values["role"] = body.role
    if not values:
        return {"ok": True}
    await session.execute(
        update(ChatGroupAgent)
        .where(
            and_(
                ChatGroupAgent.chat_group_id == group_id,
                ChatGroupAgent.agent_id == agent_id,
                ChatGroupAgent.user_id == user_id,
            )
        )
        .values(**values)
    )
    return {"ok": True}


@router.post("/{group_id}/check-removal")
async def check_agents_before_removal(
    group_id: str,
    body: CheckRemovalBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Check which agents are virtual (will be permanently deleted on removal)."""
    virtual_ids = (await session.execute(
        select(Agent.id).where(
            and_(
                Agent.id.in_(body.agent_ids),
                Agent.user_id == user_id,
                Agent.virtual == True,
            )
        )
    )).scalars().all()

    return {
        "virtual_agent_ids": list(virtual_ids),
        "non_virtual_agent_ids": [a for a in body.agent_ids if a not in set(virtual_ids)],
    }


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_group(db: AsyncSession, user_id: str, group_id: str) -> ChatGroup | None:
    stmt = select(ChatGroup).where(and_(ChatGroup.id == group_id, ChatGroup.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_group_agents(db: AsyncSession, user_id: str, group_id: str) -> list[dict[str, Any]]:
    stmt = (
        select(ChatGroupAgent, Agent)
        .join(Agent, Agent.id == ChatGroupAgent.agent_id)
        .where(and_(ChatGroupAgent.chat_group_id == group_id, ChatGroupAgent.user_id == user_id))
        .order_by(ChatGroupAgent.order)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": agent.id,
            "title": agent.title,
            "avatar": agent.avatar,
            "background_color": agent.background_color,
            "description": agent.description,
            "model": agent.model,
            "provider": agent.provider,
            "system_role": agent.system_role,
            "agent_id": cga.agent_id,
            "chat_group_id": cga.chat_group_id,
            "role": cga.role,
            "enabled": cga.enabled,
            "order": cga.order,
            "user_id": cga.user_id,
            "virtual": agent.virtual,
            "created_at": cga.created_at.isoformat() if cga.created_at else None,
            "updated_at": cga.updated_at.isoformat() if cga.updated_at else None,
        }
        for cga, agent in rows
    ]


def _group_dict(g: ChatGroup) -> dict[str, Any]:
    return {
        "id": g.id,
        "title": g.title,
        "name": g.title,
        "description": g.description,
        "avatar": g.avatar,
        "background_color": g.background_color,
        "market_identifier": g.market_identifier,
        "content": g.content,
        "editor_data": g.editor_data,
        "config": g.config,
        "client_id": g.client_id,
        "group_id": g.group_id,
        "pinned": g.pinned,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _group_values(body: CreateChatGroupBody | UpdateChatGroupBody) -> dict[str, Any]:
    values: dict[str, Any] = {}
    field_map = {
        "title": body.title if body.title is not None else body.name,
        "description": body.description,
        "avatar": body.avatar,
        "background_color": body.background_color if body.background_color is not None else body.backgroundColor,
        "market_identifier": body.market_identifier if body.market_identifier is not None else body.marketIdentifier,
        "content": body.content,
        "editor_data": body.editor_data if body.editor_data is not None else body.editorData,
        "config": body.config,
        "client_id": body.client_id if body.client_id is not None else body.clientId,
        "group_id": body.group_id if body.group_id is not None else body.groupId,
        "pinned": body.pinned,
    }
    for key, value in field_map.items():
        if value is not None:
            values[key] = value
    return values
