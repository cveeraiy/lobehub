"""Skill CRUD router — mirrors the TS agentSkills router."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import File
from app.models.skill import AgentSkill, AgentSkillShare
from app.skills.builtin import BUILTIN_SKILLS, get_builtin_skill

_VALID_VISIBILITY = ("private", "public", "restricted")

router = APIRouter(prefix="/api/skills", tags=["Skills"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slugify_skill_identifier(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:120] or "imported-skill"


def _manifest_from_text(text: str, *, source: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    name = fallback_name.rsplit(".", 1)[0] or "Imported Skill"
    return {
        "name": name,
        "description": f"Imported from {source.get('type', 'source')}",
        "prompt": text,
        "source": source,
    }


async def _save_imported_skill(
    session: AsyncSession,
    user_id: str,
    manifest: dict[str, Any],
    *,
    source: dict[str, Any],
) -> AgentSkill:
    name = str(manifest.get("name") or manifest.get("displayName") or source.get("name") or "Imported Skill")
    description = str(manifest.get("description") or "")
    identifier = _slugify_skill_identifier(str(manifest.get("identifier") or name))
    existing = (
        await session.execute(
            select(AgentSkill).where(and_(AgentSkill.identifier == identifier, AgentSkill.user_id == user_id))
        )
    ).scalar_one_or_none()
    if existing:
        existing.display_name = name
        existing.description = description
        existing.manifest = {**manifest, "source": source}
        existing.updated_at = _now()
        session.add(existing)
        await session.flush()
        return existing

    skill = AgentSkill(
        identifier=identifier,
        user_id=user_id,
        display_name=name,
        description=description,
        manifest={**manifest, "source": source},
        visibility="private",
    )
    session.add(skill)
    await session.flush()
    return skill


async def _fetch_text_url(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(url)
    if not response.is_success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to fetch skill: HTTP {response.status_code}")
    return response.text


def _github_raw_url(git_url: str, branch: str | None) -> str:
    cleaned = git_url.rstrip("/")
    if "raw.githubusercontent.com" in cleaned:
        return cleaned
    if "github.com" in cleaned:
        marker = "/blob/"
        if marker in cleaned:
            return cleaned.replace("github.com", "raw.githubusercontent.com").replace(marker, "/")
        parts = cleaned.split("github.com/", 1)[-1].split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].replace(".git", "")
            ref = branch or "main"
            suffix = "/".join(parts[2:]) if len(parts) > 2 else "SKILL.md"
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{suffix}"
    return git_url


async def _load_zip_skill_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zip file not found")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        manifest_name = next(
            (name for name in names if name.endswith("skill.json") or name.endswith("manifest.json")),
            None,
        )
        if manifest_name:
            return json.loads(archive.read(manifest_name).decode("utf-8"))
        skill_md = next((name for name in names if name.endswith("SKILL.md") or name.endswith("README.md")), None)
        if skill_md:
            return _manifest_from_text(
                archive.read(skill_md).decode("utf-8"),
                source={"type": "zip", "path": str(path)},
                fallback_name=Path(skill_md).name,
            )
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Zip does not contain skill.json, manifest.json, or SKILL.md")


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSkillBody(BaseModel):
    identifier: Optional[str] = None
    name: str
    description: str
    content: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None
    visibility: str = "private"


class UpdateSkillBody(BaseModel):
    content: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None
    visibility: Optional[str] = None


class ShareSkillBody(BaseModel):
    user_ids: list[str]


class UnshareSkillBody(BaseModel):
    user_ids: list[str]


# ── Frontend path aliases (must come before /{skill_id}) ──────────────

@router.get("/by-identifier")
async def get_skill_by_identifier_query(
    identifier: str = "",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /by-identifier?identifier=... — frontend path."""
    return await get_skill_by_identifier(identifier, user_id=user_id, session=session)


@router.get("/by-name")
async def get_skill_by_name_query(
    name: str = "",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /by-name?name=... — frontend path."""
    return await get_skill_by_name(name, user_id=user_id, session=session)


@router.get("/search")
async def search_skills_query(
    query: str = "",
    q: str = "",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /search?query=... — frontend path."""
    return await search_skills(q=query or q, user_id=user_id, session=session)


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_skills(
    source: Optional[str] = None,
    include_shared: bool = True,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List all skills (user-owned + shared/public + builtin)."""
    # 1. User's own skills
    own_stmt = (
        select(AgentSkill)
        .where(AgentSkill.user_id == user_id)
        .order_by(desc(AgentSkill.updated_at))
    )
    own_rows = (await session.execute(own_stmt)).scalars().all()
    user_skills = [_skill_dict(r) for r in own_rows]

    if source == "user":
        return user_skills

    # 2. Skills shared with this user (restricted + public)
    shared_skills: list[dict[str, Any]] = []
    if include_shared and source != "builtin":
        # Public skills from other users
        public_stmt = (
            select(AgentSkill)
            .where(
                and_(
                    AgentSkill.visibility == "public",
                    AgentSkill.user_id != user_id,
                )
            )
            .order_by(desc(AgentSkill.updated_at))
        )
        public_rows = (await session.execute(public_stmt)).scalars().all()
        shared_skills.extend([_skill_dict(r, source_label="public") for r in public_rows])

        # Restricted skills explicitly shared with this user
        restricted_stmt = (
            select(AgentSkill)
            .join(AgentSkillShare, AgentSkillShare.skill_id == AgentSkill.id)
            .where(
                and_(
                    AgentSkillShare.shared_with_user_id == user_id,
                    AgentSkill.visibility == "restricted",
                    AgentSkill.user_id != user_id,
                )
            )
            .order_by(desc(AgentSkill.updated_at))
        )
        restricted_rows = (await session.execute(restricted_stmt)).scalars().all()
        shared_skills.extend([_skill_dict(r, source_label="shared") for r in restricted_rows])

    # 3. Builtins
    seen_identifiers = {s["identifier"] for s in user_skills + shared_skills}
    builtin_skills = [
        {
            "id": None,
            "identifier": b["identifier"],
            "display_name": b["name"],
            "description": b["description"],
            "source": "builtin",
        }
        for b in BUILTIN_SKILLS
        if b["identifier"] not in seen_identifiers
    ]

    if source == "builtin":
        return builtin_skills

    if source == "shared":
        return shared_skills

    return user_skills + shared_skills + builtin_skills


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_accessible_skill(session, user_id, skill_id)
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


@router.get("/by-name/{name}")
async def get_skill_by_name(
    name: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(AgentSkill).where(
        and_(AgentSkill.display_name == name, AgentSkill.user_id == user_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    return _skill_dict(row)


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

    if body.visibility not in _VALID_VISIBILITY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid visibility: {body.visibility}. Must be one of {_VALID_VISIBILITY}",
        )

    skill = AgentSkill(
        identifier=identifier,
        user_id=user_id,
        display_name=body.name,
        description=body.description,
        manifest=manifest,
        visibility=body.visibility,
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

    if body.visibility is not None:
        if body.visibility not in _VALID_VISIBILITY:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid visibility: {body.visibility}. Must be one of {_VALID_VISIBILITY}",
            )
        values["visibility"] = body.visibility

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
    """Search skills by name/description (case-insensitive).

    Searches user-owned, public, and shared skills.
    """
    pattern = f"%{q}%"
    name_or_desc = AgentSkill.display_name.ilike(pattern) | AgentSkill.description.ilike(pattern)

    # Subquery: skill IDs shared with this user
    shared_subq = (
        select(AgentSkillShare.skill_id)
        .where(AgentSkillShare.shared_with_user_id == user_id)
        .scalar_subquery()
    )

    stmt = (
        select(AgentSkill)
        .where(
            and_(
                name_or_desc,
                or_(
                    AgentSkill.user_id == user_id,
                    AgentSkill.visibility == "public",
                    and_(
                        AgentSkill.visibility == "restricted",
                        AgentSkill.id.in_(shared_subq),
                    ),
                ),
            )
        )
        .order_by(desc(AgentSkill.updated_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_skill_dict(r) for r in rows]


# ── Import endpoints ─────────────────────────────────────────────────

class ImportFromUrlBody(BaseModel):
    url: str


class ImportFromGitHubBody(BaseModel):
    git_url: str
    branch: Optional[str] = None


class ImportFromMarketBody(BaseModel):
    identifier: str


class ImportFromZipBody(BaseModel):
    zip_file_id: str


@router.post("/import/url")
async def import_skill_from_url(
    body: ImportFromUrlBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import a skill manifest or markdown prompt from a URL."""
    text = await _fetch_text_url(body.url)
    manifest = _manifest_from_text(text, source={"type": "url", "url": body.url}, fallback_name=body.url.split("/")[-1])
    skill = await _save_imported_skill(session, user_id, manifest, source={"type": "url", "url": body.url})
    return {"id": skill.id, "identifier": skill.identifier}


@router.post("/import/github")
async def import_skill_from_github(
    body: ImportFromGitHubBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import a skill from a GitHub raw/blob/repository URL."""
    raw_url = _github_raw_url(body.git_url, body.branch)
    text = await _fetch_text_url(raw_url)
    manifest = _manifest_from_text(
        text,
        source={"type": "github", "gitUrl": body.git_url, "rawUrl": raw_url, "branch": body.branch},
        fallback_name=raw_url.split("/")[-1],
    )
    skill = await _save_imported_skill(
        session,
        user_id,
        manifest,
        source={"type": "github", "gitUrl": body.git_url, "rawUrl": raw_url, "branch": body.branch},
    )
    return {"id": skill.id, "identifier": skill.identifier}


@router.post("/import/market")
async def import_skill_from_market(
    body: ImportFromMarketBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import a builtin/market skill by identifier."""
    builtin = get_builtin_skill(body.identifier)
    if not builtin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Market skill not found")
    manifest = {
        "identifier": builtin["identifier"],
        "name": builtin["name"],
        "description": builtin["description"],
        "prompt": builtin.get("prompt"),
        "tools": builtin.get("tools", []),
    }
    skill = await _save_imported_skill(
        session,
        user_id,
        manifest,
        source={"type": "market", "identifier": body.identifier},
    )
    return {"id": skill.id, "identifier": skill.identifier}


@router.post("/import/zip")
async def import_skill_from_zip(
    body: ImportFromZipBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Import a skill from a local zip path or uploaded file record."""
    path = Path(body.zip_file_id)
    if not path.exists():
        file = (
            await session.execute(select(File).where(and_(File.id == body.zip_file_id, File.user_id == user_id)))
        ).scalar_one_or_none()
        if not file:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Zip file not found")
        path = Path(file.url)
    manifest = await _load_zip_skill_manifest(path)
    skill = await _save_imported_skill(
        session,
        user_id,
        manifest,
        source={"type": "zip", "zipFileId": body.zip_file_id},
    )
    return {"id": skill.id, "identifier": skill.identifier}


@router.get("/{skill_id}/zip-url")
async def get_skill_with_zip_url(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get skill info with its zip download URL."""
    skill = await _find_accessible_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    # Zip URL resolution would need file service
    return {"name": skill.display_name, "url": None}


@router.get("/{skill_id}/resources/content")
async def read_skill_resource_by_query(
    skill_id: str,
    path: str = "",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /{skill_id}/resources/content?path=... — frontend path."""
    return await read_skill_resource(skill_id, path, user_id=user_id, session=session)


@router.get("/{skill_id}/resources")
async def list_skill_resources(
    skill_id: str,
    include_content: bool = False,
    includeContent: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List resources for a skill."""
    skill = await _find_accessible_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    if not skill.resources:
        return []
    # Return resource paths/metadata
    want_content = include_content or includeContent
    resources = []
    for path, meta in (skill.resources or {}).items():
        entry: dict[str, Any] = {"path": path}
        if isinstance(meta, dict):
            entry.update(meta)
        if want_content and isinstance(meta, dict):
            entry["content"] = meta.get("content")
        resources.append(entry)
    return resources


@router.get("/{skill_id}/resources/{path:path}")
async def read_skill_resource(
    skill_id: str,
    path: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Read a specific resource file from a skill."""
    skill = await _find_accessible_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    if not skill.resources:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Skill has no resources")
    resource = skill.resources.get(path)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return resource


# ── Sharing endpoints ────────────────────────────────────────────────

@router.post("/{skill_id}/share", status_code=status.HTTP_201_CREATED)
async def share_skill(
    skill_id: str,
    body: ShareSkillBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Share a skill with specific users. Sets visibility to 'restricted' if currently 'private'."""
    skill = await _find_owned_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found or not owned by you")

    # Auto-set visibility to restricted if currently private
    if skill.visibility == "private":
        await session.execute(
            update(AgentSkill)
            .where(AgentSkill.id == skill_id)
            .values(visibility="restricted", updated_at=_now())
        )

    created = []
    for target_user_id in body.user_ids:
        if target_user_id == user_id:
            continue  # skip self
        # Upsert: ignore if already shared
        existing = await session.execute(
            select(AgentSkillShare).where(
                and_(
                    AgentSkillShare.skill_id == skill_id,
                    AgentSkillShare.shared_with_user_id == target_user_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        share = AgentSkillShare(
            skill_id=skill_id,
            shared_with_user_id=target_user_id,
        )
        session.add(share)
        created.append(target_user_id)

    await session.flush()
    return {"shared_with": created, "skill_id": skill_id}


@router.post("/{skill_id}/unshare")
async def unshare_skill(
    skill_id: str,
    body: UnshareSkillBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove sharing for specific users."""
    skill = await _find_owned_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found or not owned by you")

    await session.execute(
        delete(AgentSkillShare).where(
            and_(
                AgentSkillShare.skill_id == skill_id,
                AgentSkillShare.shared_with_user_id.in_(body.user_ids),
            )
        )
    )
    return {"ok": True}


@router.get("/{skill_id}/shares")
async def list_skill_shares(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List users a skill is shared with (owner only)."""
    skill = await _find_owned_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found or not owned by you")

    stmt = select(AgentSkillShare).where(AgentSkillShare.skill_id == skill_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "shared_with_user_id": r.shared_with_user_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.put("/{skill_id}/visibility")
async def update_skill_visibility(
    skill_id: str,
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update skill visibility (owner only). Body: {"visibility": "public"|"private"|"restricted"}."""
    vis = body.get("visibility", "")
    if vis not in _VALID_VISIBILITY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid visibility: {vis}. Must be one of {_VALID_VISIBILITY}",
        )

    skill = await _find_owned_skill(session, user_id, skill_id)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found or not owned by you")

    await session.execute(
        update(AgentSkill)
        .where(AgentSkill.id == skill_id)
        .values(visibility=vis, updated_at=_now())
    )

    # If set to private, remove all shares
    if vis == "private":
        await session.execute(
            delete(AgentSkillShare).where(AgentSkillShare.skill_id == skill_id)
        )

    return {"ok": True, "visibility": vis}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_owned_skill(db: AsyncSession, user_id: str, skill_id: str) -> AgentSkill | None:
    """Find a skill owned by the given user."""
    stmt = select(AgentSkill).where(
        and_(AgentSkill.id == skill_id, AgentSkill.user_id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_accessible_skill(db: AsyncSession, user_id: str, skill_id: str) -> AgentSkill | None:
    """Find a skill the user can access (owned, public, or shared)."""
    # Subquery: skill IDs shared with this user
    shared_subq = (
        select(AgentSkillShare.skill_id)
        .where(AgentSkillShare.shared_with_user_id == user_id)
        .scalar_subquery()
    )

    stmt = select(AgentSkill).where(
        and_(
            AgentSkill.id == skill_id,
            or_(
                AgentSkill.user_id == user_id,
                AgentSkill.visibility == "public",
                and_(
                    AgentSkill.visibility == "restricted",
                    AgentSkill.id.in_(shared_subq),
                ),
            ),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _skill_dict(s: AgentSkill, *, source_label: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": s.id,
        "identifier": s.identifier,
        "display_name": s.display_name,
        "description": s.description,
        "avatar": s.avatar,
        "visibility": s.visibility,
        "manifest": s.manifest,
        "resources": s.resources,
        "owner_id": s.user_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
    if source_label:
        d["source"] = source_label
    return d
