"""Knowledge Base CRUD + search router."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import knowledge_service as svc

router = APIRouter(prefix="/api/knowledge-bases", tags=["Knowledge Bases"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreateKBBody(BaseModel):
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    type: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class UpdateKBBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class SearchBody(BaseModel):
    query: str
    limit: int = 10
    model: str = "openai/text-embedding-3-small"


class BatchFilesBody(BaseModel):
    file_ids: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_kbs(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    kbs = await svc.list_knowledge_bases(session, user_id)
    return [
        {
            "id": k.id, "name": k.name, "description": k.description,
            "avatar": k.avatar, "type": k.type,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in kbs
    ]


@router.get("/{kb_id}")
async def get_kb(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    kb = await svc.get_knowledge_base(session, user_id, kb_id)
    if not kb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge base not found")
    return {
        "id": kb.id, "name": kb.name, "description": kb.description,
        "avatar": kb.avatar, "type": kb.type, "settings": kb.settings,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_kb(
    body: CreateKBBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    kb = await svc.create_knowledge_base(
        session, user_id,
        name=body.name,
        description=body.description,
        avatar=body.avatar,
        kb_type=body.type,
        settings=body.settings,
    )
    return {"id": kb.id}


@router.put("/{kb_id}")
async def update_kb(
    kb_id: str,
    body: UpdateKBBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    await svc.update_knowledge_base(session, user_id, kb_id, **values)
    return {"ok": True}


@router.delete("/{kb_id}")
async def delete_kb(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.delete_knowledge_base(session, user_id, kb_id)
    return {"ok": True}


# ── File association ─────────────────────────────────────────────────

@router.get("/{kb_id}/files")
async def list_kb_files(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await svc.list_kb_files(session, user_id, kb_id)


@router.post("/{kb_id}/files/{file_id}", status_code=status.HTTP_201_CREATED)
async def add_file(
    kb_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.add_file_to_kb(session, user_id, kb_id, file_id)
    return {"ok": True}


@router.delete("/{kb_id}/files/{file_id}")
async def remove_file(
    kb_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.remove_file_from_kb(session, user_id, kb_id, file_id)
    return {"ok": True}


@router.post("/{kb_id}/files", status_code=status.HTTP_201_CREATED)
async def add_files(
    kb_id: str,
    body: BatchFilesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Add multiple files to a knowledge base."""
    for fid in body.file_ids:
        await svc.add_file_to_kb(session, user_id, kb_id, fid)
    return {"ok": True, "count": len(body.file_ids)}


@router.post("/{kb_id}/files/batch-remove")
async def remove_files(
    kb_id: str,
    body: BatchFilesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove multiple files from a knowledge base."""
    for fid in body.file_ids:
        await svc.remove_file_from_kb(session, user_id, kb_id, fid)
    return {"ok": True, "count": len(body.file_ids)}


@router.delete("")
async def delete_all_kbs(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all knowledge bases for the user."""
    await svc.delete_all_knowledge_bases(session, user_id)
    return {"ok": True}


# ── Search ───────────────────────────────────────────────────────────

@router.post("/{kb_id}/search")
async def search_kb(
    kb_id: str,
    body: SearchBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from app.services import llm_service
    vectors = await llm_service.embed([body.query], model=body.model)
    results = await svc.vector_search(
        session, user_id, vectors[0], kb_id=kb_id, limit=body.limit
    )
    return results
