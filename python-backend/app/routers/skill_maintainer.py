"""Skill Maintainer router for Agent Signal file operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.skill_maintainer import SkillMaintainerService, assert_package_relative_path

router = APIRouter(prefix="/api/skill-maintainer", tags=["Skill Maintainer"])


class SkillFileBody(BaseModel):
    skill_ref: str
    path: str
    content: str | None = None


def _service(session: AsyncSession, user_id: str) -> SkillMaintainerService:
    return SkillMaintainerService(session, user_id)


@router.post("/read")
async def read_skill_file(
    body: SkillFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        content = await _service(session, user_id).read_skill_file(skill_ref=body.skill_ref, path=body.path)
        return {"content": content, "path": assert_package_relative_path(body.path), "skillRef": body.skill_ref}
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill file not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/update")
async def update_skill(
    body: SkillFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.content is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "content is required")
    try:
        await _service(session, user_id).update_skill(skill_ref=body.skill_ref, path=body.path, content=body.content)
        return {"path": assert_package_relative_path(body.path), "skillRef": body.skill_ref, "success": True}
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill file not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/write")
async def write_skill_file(
    body: SkillFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.content is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "content is required")
    try:
        await _service(session, user_id).write_skill_file(
            skill_ref=body.skill_ref,
            path=body.path,
            content=body.content,
        )
        return {"path": assert_package_relative_path(body.path), "skillRef": body.skill_ref, "success": True}
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/remove")
async def remove_skill_file(
    body: SkillFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        await _service(session, user_id).remove_skill_file(skill_ref=body.skill_ref, path=body.path)
        return {"path": assert_package_relative_path(body.path), "skillRef": body.skill_ref, "success": True}
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill file not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
