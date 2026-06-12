"""Agent Document VFS Router — REST endpoints for the virtual filesystem.

Mirrors the tRPC procedures in the TypeScript codebase at
src/server/routers/lambda/agentDocumentVfs.ts
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.agent_document_vfs import AgentDocumentVfsError, AgentDocumentVfsService
from app.services.agent_document_vfs.types import AgentDocumentListOptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-document-vfs", tags=["Agent Document VFS"])

_STATUS_MAP = {
    "BAD_REQUEST": 400,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "METHOD_NOT_SUPPORTED": 405,
}


def _handle(exc: AgentDocumentVfsError) -> HTTPException:
    return HTTPException(status_code=_STATUS_MAP.get(exc.code, 400), detail=str(exc))


# ── Schemas ──────────────────────────────────────────────────────────

class ListBody(BaseModel):
    agent_id: str
    path: str = "."
    cursor: Optional[str] = None
    detail: Optional[str] = "basic"
    limit: Optional[int] = None


class StatBody(BaseModel):
    agent_id: str
    path: str


class ReadBody(BaseModel):
    agent_id: str
    path: str


class WriteBody(BaseModel):
    agent_id: str
    path: str
    content: str
    file_type: Optional[str] = "agent/document"
    title: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    editor_data: Optional[dict[str, Any]] = None


class MkdirBody(BaseModel):
    agent_id: str
    path: str


class RenameBody(BaseModel):
    agent_id: str
    from_path: str
    to_path: str


class CopyBody(BaseModel):
    agent_id: str
    from_path: str
    to_path: Optional[str] = None


class DeleteBody(BaseModel):
    agent_id: str
    path: str
    reason: Optional[str] = None


class TrashRestoreBody(BaseModel):
    agent_id: str
    agent_document_id: str


class TrashDeleteBody(BaseModel):
    agent_id: str
    agent_document_id: str


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/list")
async def vfs_list(
    body: ListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        opts = AgentDocumentListOptions(
            cursor=body.cursor,
            detail=body.detail if body.detail in ("basic", "full") else "basic",  # type: ignore[arg-type]
            limit=body.limit,
        )
        return await svc.list(body.agent_id, body.path, opts)
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/stat")
async def vfs_stat(
    body: StatBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        return await svc.stat(body.agent_id, body.path)
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/read")
async def vfs_read(
    body: ReadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        result = await svc.read(body.agent_id, body.path)
        return {
            "content": result.content,
            "path": result.path,
            "contentType": result.content_type,
        }
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/write")
async def vfs_write(
    body: WriteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        return await svc.write(
            body.agent_id,
            body.path,
            body.content,
            file_type=body.file_type or "agent/document",
            title=body.title,
            metadata=body.metadata,
            editor_data=body.editor_data,
        )
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/mkdir")
async def vfs_mkdir(
    body: MkdirBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        return await svc.mkdir(body.agent_id, body.path)
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/rename")
async def vfs_rename(
    body: RenameBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        return await svc.rename(body.agent_id, body.from_path, body.to_path)
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/copy")
async def vfs_copy(
    body: CopyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        return await svc.copy(body.agent_id, body.from_path, body.to_path)
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/delete")
async def vfs_delete(
    body: DeleteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        await svc.delete(body.agent_id, body.path, reason=body.reason)
        return {"ok": True}
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/trash/list")
async def vfs_trash_list(
    body: StatBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    return await svc.list_trash(body.agent_id)


@router.post("/trash/restore")
async def vfs_trash_restore(
    body: TrashRestoreBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        await svc.restore_from_trash(body.agent_id, body.agent_document_id)
        return {"ok": True}
    except AgentDocumentVfsError as exc:
        raise _handle(exc)


@router.post("/trash/delete")
async def vfs_trash_delete(
    body: TrashDeleteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentDocumentVfsService(session, user_id)
    try:
        await svc.delete_permanently(body.agent_id, body.agent_document_id)
        return {"ok": True}
    except AgentDocumentVfsError as exc:
        raise _handle(exc)
