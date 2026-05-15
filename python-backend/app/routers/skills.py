"""Skill CRUD router — mirrors the TS agentSkills router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.skill import AgentSkill
from app.skills.builtin import BUILTIN_SKILLS, get_builtin_skill

router = APIRouter(prefix="/api/skills", tags=["Skills"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSkillBody(BaseModel):
    identifier: Optional[str] = None
    name: str
    description: str
    content: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None


class UpdateSkillBody(BaseModel):
    content: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_skills(
    source: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List all skills (user + builtin)."""
    stmt = (
        select(AgentSkill)
        .where(AgentSkill.user_id == user_id)
        .order_by(desc(AgentSkill.updated_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    user_skills = [_skill_dict(r) for r in rows]

    if source == "user":
        return user_skills

    # Merge builtins (only those not overridden by user)
    user_ids = {s["identifier"] for s in user_skills}
    builtin_skills = [
        {
            "id": None,
            "identifier": b["identifier"],
            "display_name": b["name"],
            "description": b["description"],
            "source": "builtin",
        }
        for b in BUILTIN_SKILLS
        if b["identifier"] not in user_ids
    ]

    if source == "builtin":
        return builtin_skills

    return user_skills + builtin_skills


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_skill(session, user_id, skill_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    return _skill_dict(row)


@router.get("/by-identifier/{identifier}")
async def get_skill_by_identifier(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(AgentSkill).where(
        and_(AgentSkill.identifier == identifier, AgentSkill.user_id == user_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return _skill_dict(row)

    # Fall back to builtin
    builtin = get_builtin_skill(identifier)
    if builtin:
        return {
            "id": None,
            "identifier": builtin["identifier"],
            "display_name": builtin["name"],
            "description": builtin["description"],
            "manifest": {
                "name": builtin["name"],
                "description": builtin["description"],
                "prompt": builtin["prompt"],
                "tools": builtin.get("tools", []),
            },
            "source": "builtin",
        }

    raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: CreateSkillBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    identifier = body.identifier or body.name.lower().replace(" ", "-")

    manifest = body.manifest or {}
    manifest.setdefault("name", body.name)
    manifest.setdefault("description", body.description)
    if body.content:
        manifest.setdefault("prompt", body.content)

    skill = AgentSkill(
        identifier=identifier,
        user_id=user_id,
        display_name=body.name,
        description=body.description,
        manifest=manifest,
    )
    session.add(skill)
    await session.flush()
    return {"id": skill.id, "identifier": identifier}


@router.put("/{skill_id}")
async def update_skill(
    skill_id: str,
    body: UpdateSkillBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {"updated_at": _now()}

    if body.manifest is not None:
        values["manifest"] = body.manifest
        # Sync top-level fields from manifest
        if "name" in body.manifest:
            values["display_name"] = body.manifest["name"]
        if "description" in body.manifest:
            values["description"] = body.manifest["description"]

    stmt = (
        update(AgentSkill)
        .where(and_(AgentSkill.id == skill_id, AgentSkill.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(AgentSkill).where(
            and_(AgentSkill.id == skill_id, AgentSkill.user_id == user_id)
        )
    )
    return {"ok": True}


@router.get("/search/query")
async def search_skills(
    q: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Search skills by name/description (case-insensitive)."""
    pattern = f"%{q}%"
    stmt = (
        select(AgentSkill)
        .where(
            and_(
                AgentSkill.user_id == user_id,
                (AgentSkill.display_name.ilike(pattern) | AgentSkill.description.ilike(pattern)),
            )
        )
        .order_by(desc(AgentSkill.updated_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_skill_dict(r) for r in rows]


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_skill(db: AsyncSession, user_id: str, skill_id: str) -> AgentSkill | None:
    stmt = select(AgentSkill).where(
        and_(AgentSkill.id == skill_id, AgentSkill.user_id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _skill_dict(s: AgentSkill) -> dict[str, Any]:
    return {
        "id": s.id,
        "identifier": s.identifier,
        "display_name": s.display_name,
        "description": s.description,
        "avatar": s.avatar,
        "manifest": s.manifest,
        "resources": s.resources,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
