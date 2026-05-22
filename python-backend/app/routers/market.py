"""Marketplace router — browse/search community agents, install from market."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user_id
from app.models._helpers import create_nanoid
from app.models.agent import Agent
from app.models.user import UserSettings
from app.services.key_vault.service import KeyVaultService

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


def _now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat()


async def _get_or_create_user_settings(session: AsyncSession, user_id: str) -> UserSettings:
    settings_row = (
        await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()
    if settings_row is not None:
        return settings_row
    settings_row = UserSettings(user_id=user_id, market={"creds": [], "files": {}, "oauthConnections": []})
    session.add(settings_row)
    await session.flush()
    return settings_row


def _market_state(settings_row: UserSettings) -> dict[str, Any]:
    state = dict(settings_row.market or {})
    state.setdefault("creds", [])
    state.setdefault("files", {})
    state.setdefault("oauthConnections", [])
    return state


def _save_market_state(settings_row: UserSettings, state: dict[str, Any]) -> None:
    settings_row.market = state
    settings_row.updated_at = datetime.now(UTC).replace(tzinfo=None)


def _next_cred_id(creds: list[dict[str, Any]]) -> int:
    ids = [int(cred.get("id") or 0) for cred in creds if str(cred.get("id") or "").isdigit()]
    return max(ids, default=0) + 1


def _find_cred(creds: list[dict[str, Any]], cred_id: int) -> dict[str, Any] | None:
    return next((cred for cred in creds if int(cred.get("id") or 0) == cred_id), None)


def _find_cred_by_key(creds: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next((cred for cred in creds if cred.get("key") == key), None)


def _encode_secret(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if not values:
        return None
    if settings.key_vaults_secret:
        return {"encoding": "key-vault", "value": KeyVaultService.from_env().encrypt_json(values)}
    return {"encoding": "plain", "value": values}


def _decode_secret(secret: dict[str, Any] | None) -> dict[str, Any]:
    if not secret:
        return {}
    if secret.get("encoding") == "key-vault":
        return KeyVaultService.from_env().decrypt_json(str(secret.get("value") or ""))
    value = secret.get("value")
    return value if isinstance(value, dict) else {}


def _public_cred(cred: dict[str, Any], *, decrypt: bool = False) -> dict[str, Any]:
    public = {key: value for key, value in cred.items() if key not in {"secret"}}
    public["hasSecret"] = bool(cred.get("secret"))
    if decrypt:
        public["plaintext"] = _decode_secret(cred.get("secret"))
    return public


def _cred_from_body(body: CredBody, cred_id: int, cred_type: str) -> dict[str, Any]:
    now = _now_iso()
    payload = body.model_dump(exclude_none=True)
    values = payload.pop("values", None)
    return {
        **payload,
        "id": cred_id,
        "type": body.type or cred_type,
        "secret": _encode_secret(values),
        "createdAt": now,
        "updatedAt": now,
    }


def _file_hash(content: str) -> str:
    try:
        raw = base64.b64decode(content, validate=True)
    except Exception:
        raw = content.encode()
    return hashlib.sha256(raw).hexdigest()


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
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    return {"data": [_public_cred(cred) for cred in state["creds"]]}


@router.get("/creds/by-key/{key}")
async def get_market_cred_by_key(
    key: str,
    decrypt: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    cred = _find_cred_by_key(_market_state(settings_row)["creds"], key)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    return _public_cred(cred, decrypt=decrypt)


@router.delete("/creds/by-key/{key}")
async def delete_market_cred_by_key(
    key: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    cred = _find_cred_by_key(state["creds"], key)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    state["creds"] = [item for item in state["creds"] if item.get("key") != key]
    _save_market_state(settings_row, state)
    return {"id": cred["id"], "success": True}


@router.delete("/creds/{cred_id}")
async def delete_market_cred(
    cred_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    original_len = len(state["creds"])
    state["creds"] = [cred for cred in state["creds"] if int(cred.get("id") or 0) != cred_id]
    if len(state["creds"]) == original_len:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    _save_market_state(settings_row, state)
    return {"id": cred_id, "success": True}


@router.put("/creds/{cred_id}")
async def update_market_cred(
    cred_id: int,
    body: CredBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    cred = _find_cred(state["creds"], cred_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    updates = body.model_dump(exclude_none=True)
    values = updates.pop("values", None)
    cred.update(updates)
    if values is not None:
        cred["secret"] = _encode_secret(values)
    cred["updatedAt"] = _now_iso()
    _save_market_state(settings_row, state)
    return {"data": _public_cred(cred), "id": cred_id, "success": True}


@router.post("/creds/kv")
async def create_kv_cred(
    body: CredBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    cred = _cred_from_body(body, _next_cred_id(state["creds"]), "kv")
    state["creds"].append(cred)
    _save_market_state(settings_row, state)
    return {"data": _public_cred(cred), "id": cred["id"], "success": True}


@router.post("/creds/file")
async def create_file_cred(
    body: CredBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    cred = _cred_from_body(body, _next_cred_id(state["creds"]), "file")
    state["creds"].append(cred)
    _save_market_state(settings_row, state)
    return {"data": _public_cred(cred), "id": cred["id"], "success": True}


@router.post("/creds/upload")
async def upload_cred_file(
    body: UploadCredFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    hash_id = _file_hash(body.file)
    state["files"][hash_id] = {
        "content": body.file,
        "fileName": body.file_name,
        "fileType": body.file_type,
        "hashId": hash_id,
        "updatedAt": _now_iso(),
    }
    _save_market_state(settings_row, state)
    return {"fileHashId": hash_id, "fileName": body.file_name}


@router.get("/creds/oauth-connections")
async def list_oauth_connections(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    return {"connections": _market_state(settings_row)["oauthConnections"]}


@router.post("/creds/oauth")
async def create_oauth_cred(
    body: CredBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    state = _market_state(settings_row)
    cred = _cred_from_body(body, _next_cred_id(state["creds"]), "oauth")
    state["creds"].append(cred)
    if body.oauth_connection_id is not None:
        state["oauthConnections"].append(
            {
                "credentialId": cred["id"],
                "id": body.oauth_connection_id,
                "key": body.key,
                "name": body.name,
                "updatedAt": _now_iso(),
            }
        )
    _save_market_state(settings_row, state)
    return {"data": _public_cred(cred), "id": cred["id"], "success": True}


@router.post("/creds/inject")
async def inject_market_creds(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    keys = body.get("keys") or body.get("credentialKeys") or []
    settings_row = await _get_or_create_user_settings(session, user_id)
    creds = _market_state(settings_row)["creds"]
    injected = {
        key: _decode_secret(cred.get("secret"))
        for key in keys
        if (cred := _find_cred_by_key(creds, str(key))) is not None
    }
    return {"data": injected}


@router.get("/creds/skill-status")
async def get_skill_cred_status(
    keys: list[str] = Query(default=[]),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    creds = _market_state(settings_row)["creds"]
    return {"data": {key: _find_cred_by_key(creds, key) is not None for key in keys}}


@router.get("/creds/{cred_id}")
async def get_market_cred(
    cred_id: int,
    decrypt: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    settings_row = await _get_or_create_user_settings(session, user_id)
    cred = _find_cred(_market_state(settings_row)["creds"], cred_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    return _public_cred(cred, decrypt=decrypt)


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
