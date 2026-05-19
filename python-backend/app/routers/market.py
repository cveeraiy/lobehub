"""Marketplace router — browse/search community agents, install from market."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models._helpers import create_nanoid
from app.models.agent import Agent

router = APIRouter(prefix="/api/market", tags=["Market"])


class InstallAgentBody(BaseModel):
    identifier: str
    title: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_role: Optional[str] = None
    model: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class IdentifierBody(BaseModel):
    identifier: str


class PublishAgentBody(BaseModel):
    avatar: Optional[str] = None
    changelog: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = None
    identifier: Optional[str] = None
    name: str
    tags: Optional[list[str]] = None
    token_usage: Optional[int] = None


class PublishAgentGroupBody(BaseModel):
    avatar: Optional[str] = None
    background_color: Optional[str] = None
    category: Optional[str] = None
    changelog: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    description: str
    identifier: Optional[str] = None
    member_agents: list[dict[str, Any]] = []
    name: str
    visibility: Optional[str] = None


class CredBody(BaseModel):
    description: Optional[str] = None
    file_hash_id: Optional[str] = None
    file_name: Optional[str] = None
    key: Optional[str] = None
    name: Optional[str] = None
    oauth_connection_id: Optional[int] = None
    type: Optional[str] = None
    values: Optional[dict[str, Any]] = None


class UploadCredFileBody(BaseModel):
    file: str
    file_name: str
    file_type: Optional[str] = None


class FeedbackClientInfo(BaseModel):
    language: Optional[str] = None
    timezone: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None


class SubmitFeedbackBody(BaseModel):
    client_info: Optional[FeedbackClientInfo] = None
    email: Optional[str] = None
    message: str
    screenshot_url: Optional[str] = None
    title: str


def _market_identifier() -> str:
    return create_nanoid(8)


def _ownership_result(identifier: str, original_key: str) -> dict[str, Any]:
    return {
        "exists": bool(identifier),
        "isOwner": True,
        original_key: None,
    }


@router.get("/agents")
async def browse_market_agents(
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Browse agents available in the marketplace.

    For now, this returns agents that have a `market_identifier` set,
    indicating they've been published. In the future this would query an
    external market API.
    """
    stmt = select(Agent).where(Agent.market_identifier.isnot(None))
    if keyword:
        pattern = f"%{keyword}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Agent.title.ilike(pattern),
                Agent.description.ilike(pattern),
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_market_agent_dict(a) for a in rows]


@router.post("/agents/install", status_code=status.HTTP_201_CREATED)
async def install_market_agent(
    body: InstallAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Install (fork) an agent from the marketplace into the user's collection."""
    # Check if already installed
    existing = (
        await session.execute(
            select(Agent).where(
                and_(Agent.market_identifier == body.identifier, Agent.user_id == user_id)
            )
        )
    ).scalar_one_or_none()

    if existing:
        return {"id": existing.id, "already_installed": True}

    agent = Agent(
        user_id=user_id,
        slug=body.identifier,
        market_identifier=body.identifier,
        title=body.title,
        description=body.description,
        avatar=body.avatar,
        system_role=body.system_role,
        model=body.model,
        tags=body.tags,
    )
    session.add(agent)
    await session.flush()
    return {"id": agent.id, "already_installed": False}


@router.delete("/agents/{identifier}")
async def uninstall_market_agent(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove a market-installed agent from the user's collection."""
    from sqlalchemy import delete
    await session.execute(
        delete(Agent).where(
            and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
        )
    )
    return {"ok": True}


@router.get("/creds/list")
async def list_market_creds(
    _user_id: str = Depends(get_current_user_id),
):
    """Return credential summaries for context injection.

    The Python backend does not own marketplace credentials yet. Returning an
    empty list preserves the optional context contract without falling back to
    tRPC from REST chat runtime paths.
    """
    return {"data": []}


@router.get("/creds/{cred_id}")
async def get_market_cred(cred_id: int, decrypt: bool = False):
    return {"id": cred_id, "plaintext": {} if decrypt else None}


@router.delete("/creds/{cred_id}")
async def delete_market_cred(cred_id: int):
    return {"id": cred_id, "success": True}


@router.put("/creds/{cred_id}")
async def update_market_cred(cred_id: int, body: CredBody):
    return {"id": cred_id, "success": True, **body.model_dump(exclude_none=True)}


@router.post("/creds/kv")
async def create_kv_cred(body: CredBody):
    return {"id": 0, "success": True, **body.model_dump(exclude_none=True)}


@router.post("/creds/file")
async def create_file_cred(body: CredBody):
    return {"id": 0, "success": True, **body.model_dump(exclude_none=True)}


@router.post("/creds/upload")
async def upload_cred_file(body: UploadCredFileBody):
    return {"fileHashId": create_nanoid(12), "fileName": body.file_name}


@router.get("/creds/oauth-connections")
async def list_oauth_connections():
    return {"connections": []}


@router.post("/creds/oauth")
async def create_oauth_cred(body: CredBody):
    return {"id": 0, "success": True, **body.model_dump(exclude_none=True)}


@router.get("/agent/check-ownership")
async def check_agent_ownership(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    existing = (
        await session.execute(
            select(Agent).where(
                and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
            )
        )
    ).scalar_one_or_none()
    if not existing:
        return {"exists": False, "isOwner": False, "originalAgent": None}
    return _ownership_result(identifier, "originalAgent")


@router.post("/agent")
async def create_market_agent(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    identifier = str(body.get("identifier") or _market_identifier())
    agent = Agent(
        user_id=user_id,
        slug=identifier,
        market_identifier=identifier,
        title=str(body.get("name") or body.get("title") or identifier),
        description=body.get("description"),
        avatar=body.get("avatar"),
        tags=body.get("tags"),
    )
    session.add(agent)
    await session.flush()
    return {"id": agent.id, "identifier": identifier, "success": True}


@router.get("/agent/detail")
async def get_market_agent_detail(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    agent = (
        await session.execute(
            select(Agent).where(
                and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
            )
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Market agent not found")
    return {
        **_market_agent_dict(agent),
        "id": agent.id,
        "name": agent.title,
        "status": "published",
    }


@router.get("/agent/onboarding-full")
async def get_onboarding_agents(
    _user_id: str = Depends(get_current_user_id),
):
    """Return market-backed onboarding agent templates.

    The hosted market catalog is still TypeScript-owned. Returning an empty
    category map keeps the REST onboarding flow functional until Python owns
    catalog synchronization.
    """
    return {}


@router.post("/agent/version")
async def create_market_agent_version(body: dict[str, Any]):
    return {
        "identifier": body.get("identifier"),
        "success": True,
        "version": body.get("version") or "latest",
    }


@router.post("/agent/publish")
async def publish_market_agent(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.post("/agent/unpublish")
async def unpublish_market_agent(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.post("/agent/deprecate")
async def deprecate_market_agent(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.get("/agent/own")
async def get_own_market_agents(
    page: int = 1,
    pageSize: int = Query(default=20, alias="pageSize"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    limit = min(pageSize, 100)
    offset = max(page - 1, 0) * limit
    rows = (
        await session.execute(
            select(Agent)
            .where(and_(Agent.market_identifier.isnot(None), Agent.user_id == user_id))
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    items = [_market_agent_dict(agent) | {"id": agent.id, "name": agent.title} for agent in rows]
    return {"items": items, "page": page, "pageSize": limit, "total": len(items)}


@router.post("/agent/fork")
async def fork_market_agent(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    source_identifier = str(body.get("sourceIdentifier") or body.get("source_identifier") or "")
    identifier = _market_identifier()
    title = str(body.get("name") or body.get("title") or source_identifier or identifier)
    agent = Agent(
        user_id=user_id,
        slug=identifier,
        market_identifier=identifier,
        title=title,
        description=body.get("description"),
        avatar=body.get("avatar"),
        tags=body.get("tags"),
    )
    session.add(agent)
    await session.flush()
    return {
        "agentId": agent.id,
        "forkedFromAgentId": source_identifier or None,
        "identifier": identifier,
        "success": True,
    }


@router.get("/agent/forks")
async def get_market_agent_forks(identifier: str):
    return {"identifier": identifier, "items": [], "total": 0}


@router.get("/agent/fork-source")
async def get_market_agent_fork_source(identifier: str):
    return {"identifier": identifier, "source": None}


@router.post("/agent/publish-or-create")
async def publish_or_create_agent(
    body: PublishAgentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    identifier = body.identifier
    is_new_agent = False
    existing = None
    if identifier:
        existing = (
            await session.execute(
                select(Agent).where(
                    and_(Agent.market_identifier == identifier, Agent.user_id == user_id)
                )
            )
        ).scalar_one_or_none()

    if not identifier or not existing:
        identifier = _market_identifier()
        is_new_agent = True

    values = {
        "avatar": body.avatar,
        "description": body.description,
        "editor_data": body.editor_data,
        "market_identifier": identifier,
        "tags": body.tags,
        "title": body.name,
    }
    if existing:
        await session.execute(
            update(Agent).where(Agent.id == existing.id).values(**values)
        )

    return {"identifier": identifier, "isNewAgent": is_new_agent, "success": True}


@router.get("/agent-group/check-ownership")
async def check_agent_group_ownership(identifier: str):
    return _ownership_result(identifier, "originalGroup")


@router.get("/agent-group/detail")
async def get_market_agent_group_detail(identifier: str):
    return {
        "identifier": identifier,
        "memberAgents": [],
        "name": identifier,
        "status": "published",
    }


@router.post("/agent-group/publish-or-create")
async def publish_or_create_agent_group(body: PublishAgentGroupBody):
    identifier = body.identifier or _market_identifier()
    return {
        "identifier": identifier,
        "isNewGroup": not body.identifier,
        "success": True,
    }


@router.post("/agent-group/publish")
async def publish_market_agent_group(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.post("/agent-group/unpublish")
async def unpublish_market_agent_group(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.post("/agent-group/deprecate")
async def deprecate_market_agent_group(body: IdentifierBody):
    return {"identifier": body.identifier, "success": True}


@router.post("/agent-group/fork")
async def fork_market_agent_group(body: dict[str, Any]):
    source_identifier = str(body.get("sourceIdentifier") or body.get("source_identifier") or "")
    return {
        "forkedFromGroupId": source_identifier or None,
        "identifier": _market_identifier(),
        "success": True,
    }


@router.get("/agent-group/forks")
async def get_market_agent_group_forks(identifier: str):
    return {"identifier": identifier, "items": [], "total": 0}


@router.get("/agent-group/fork-source")
async def get_market_agent_group_fork_source(identifier: str):
    return {"identifier": identifier, "source": None}


@router.post("/feedback")
async def submit_feedback(
    body: SubmitFeedbackBody,
    _user_id: str = Depends(get_current_user_id),
):
    """Accept user feedback through the Python REST path.

    The TypeScript backend forwards this to the hosted market feedback service.
    Python keeps the same frontend contract so REST-enabled clients do not fall
    back to tRPC for feedback submission.
    """
    if not body.title.strip() or not body.message.strip():
        raise HTTPException(status_code=400, detail="Feedback title and message are required")
    return {"success": True}


@router.get("/skill/list")
async def list_market_skills(
    page: int = 1,
    pageSize: int = Query(default=20, alias="pageSize"),
):
    return {
        "items": [],
        "page": page,
        "pageSize": min(pageSize, 100),
        "total": 0,
    }


def _market_agent_dict(a: Agent) -> dict[str, Any]:
    return {
        "identifier": a.market_identifier,
        "title": a.title,
        "description": a.description,
        "avatar": a.avatar,
        "tags": a.tags,
        "model": a.model,
        "author_id": a.user_id,
    }
