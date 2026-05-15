"""File upload / list / delete router."""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import File
from app.services.file_service import S3Client, create_file_record, delete_file_record, get_file_by_id

router = APIRouter(prefix="/api/files", tags=["Files"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreatePresignedUrlBody(BaseModel):
    key: str


class CreateFileRecordBody(BaseModel):
    name: str
    url: str
    file_type: str
    size: int
    file_hash: str
    metadata: Optional[dict[str, Any]] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_files(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(File)
        .where(File.user_id == user_id)
        .order_by(desc(File.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_file_dict(r) for r in rows]


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    f = await get_file_by_id(session, user_id, file_id)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return _file_dict(f)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Upload a file to S3 and create the DB record with dedup."""
    data = await file.read()
    file_hash = hashlib.sha256(data).hexdigest()
    content_type = file.content_type or "application/octet-stream"

    s3 = S3Client.from_settings()
    key = f"files/{user_id}/{file_hash[:8]}_{file.filename}"
    s3.upload_bytes(key, data, content_type)

    result = await create_file_record(
        session, user_id,
        name=file.filename or "upload",
        url=key,
        file_type=content_type,
        size=len(data),
        file_hash=file_hash,
    )
    return result


@router.post("/presigned-url")
async def create_presigned_url(
    body: CreatePresignedUrlBody,
    user_id: str = Depends(get_current_user_id),
):
    """Return a presigned upload URL for direct client-side upload."""
    s3 = S3Client.from_settings()
    url = s3.create_presigned_upload_url(body.key)
    return {"url": url}


@router.post("/record", status_code=status.HTTP_201_CREATED)
async def create_record(
    body: CreateFileRecordBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a file DB record (after client-side upload via presigned URL)."""
    return await create_file_record(
        session, user_id,
        name=body.name,
        url=body.url,
        file_type=body.file_type,
        size=body.size,
        file_hash=body.file_hash,
        metadata=body.metadata,
    )


@router.delete("/{file_id}")
async def remove_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    f = await get_file_by_id(session, user_id, file_id)
    if f:
        try:
            s3 = S3Client.from_settings()
            s3.delete_file(f.url)
        except Exception:
            pass  # Best-effort S3 delete
    await delete_file_record(session, user_id, file_id)
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _file_dict(f: File) -> dict[str, Any]:
    return {
        "id": f.id,
        "name": f.name,
        "url": f.url,
        "file_type": f.file_type,
        "size": f.size,
        "file_hash": f.file_hash,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
