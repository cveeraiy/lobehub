"""Managed skill file operations for Agent Signal maintenance workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import AgentSkill


def assert_package_relative_path(path: str) -> str:
    if path.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    segments = [segment for segment in path.split("/") if segment]
    if any(segment == ".." for segment in segments):
        raise ValueError("path traversal is not allowed")
    return "/".join(segments)


@dataclass(frozen=True)
class ManagedSkillReference:
    id: str
    kind: str
    root_path: str
    scope: str
    writable: bool


class SkillMaintainerService:
    """Apply path-safe file operations to user-owned agent skills."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    async def resolve(self, skill_ref: str) -> tuple[AgentSkill, ManagedSkillReference]:
        skill = (
            await self._db.execute(
                select(AgentSkill).where(and_(AgentSkill.id == skill_ref, AgentSkill.user_id == self._uid))
            )
        ).scalar_one_or_none()
        if skill is None:
            skill = (
                await self._db.execute(
                    select(AgentSkill).where(
                        and_(AgentSkill.identifier == skill_ref, AgentSkill.user_id == self._uid)
                    )
                )
            ).scalar_one_or_none()
        if skill is None:
            raise ValueError(f"Unknown skill reference: {skill_ref}")
        return skill, ManagedSkillReference(
            id=skill.id,
            kind="agent-skill",
            root_path=f"./lobe/skills/agent/skills/{skill.id}",
            scope="agent",
            writable=True,
        )

    async def read_skill_file(self, *, skill_ref: str, path: str) -> str:
        skill, _ = await self.resolve(skill_ref)
        file_path = assert_package_relative_path(path)
        files = _resource_files(skill)
        if file_path not in files:
            raise FileNotFoundError(file_path)
        return str(files[file_path])

    async def update_skill(self, *, skill_ref: str, path: str, content: str) -> None:
        await self.read_skill_file(skill_ref=skill_ref, path=path)
        await self.write_skill_file(skill_ref=skill_ref, path=path, content=content)

    async def write_skill_file(self, *, skill_ref: str, path: str, content: str) -> None:
        skill, _ = await self.resolve(skill_ref)
        file_path = assert_package_relative_path(path)
        resources = dict(skill.resources or {})
        files = dict(resources.get("files") or {})
        files[file_path] = content
        resources["files"] = files
        skill.resources = resources
        skill.updated_at = _now()
        self._db.add(skill)
        await self._db.flush()

    async def remove_skill_file(self, *, skill_ref: str, path: str) -> None:
        skill, _ = await self.resolve(skill_ref)
        file_path = assert_package_relative_path(path)
        resources = dict(skill.resources or {})
        files = dict(resources.get("files") or {})
        if file_path not in files:
            raise FileNotFoundError(file_path)
        files.pop(file_path)
        resources["files"] = files
        skill.resources = resources
        skill.updated_at = _now()
        self._db.add(skill)
        await self._db.flush()


def _resource_files(skill: AgentSkill) -> dict[str, str]:
    resources = skill.resources or {}
    files = resources.get("files") if isinstance(resources, dict) else None
    return files if isinstance(files, dict) else {}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
