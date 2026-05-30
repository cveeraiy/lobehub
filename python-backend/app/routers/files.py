"""File upload / list / delete router."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import Document, File
from app.models.misc import AsyncTask
from app.models.rag import DocumentChunk
from app.services.file_service import S3Client, create_file_record, delete_file_record, get_file_by_id

router = APIRouter(prefix="/api/files", tags=["Files"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


class UpdateFileBody(BaseModel):
    name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    parentId: Optional[str] = None
    parent_id: Optional[str] = None


class CreateFileBody(BaseModel):
    """Body for POST /files — matches frontend createFile."""
    name: Optional[str] = None
    url: str
    file_type: Optional[str] = None
    fileType: Optional[str] = None
    size: Optional[int] = None
    hash: Optional[str] = None
    file_hash: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    knowledgeBaseId: Optional[str] = None
    parentId: Optional[str] = None


class BatchDeleteBody(BaseModel):
    ids: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_file(
    body: CreateFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a file record — frontend POST /files."""
    result = await create_file_record(
        session, user_id,
        name=body.name or "Untitled",
        url=body.url,
        file_type=body.fileType or body.file_type or "application/octet-stream",
        size=body.size or 0,
        file_hash=body.file_hash or body.hash or "",
        metadata=body.metadata,
    )
    # Set parent_id if provided (knowledge base association)
    file_id = result.get("file_id") or result.get("id")
    if body.parentId and file_id:
        await session.execute(
            update(File).where(File.id == file_id).values(parent_id=body.parentId)
        )
    return result


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
    await s3.upload_bytes(key, data, content_type)

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
    url = await s3.create_presigned_upload_url(body.key)
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
            await s3.delete_file(f.url)
        except Exception:
            pass  # Best-effort S3 delete
    await delete_file_record(session, user_id, file_id)
    return {"ok": True}


@router.put("/{file_id}")
async def update_file(
    file_id: str,
    body: UpdateFileBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update file metadata (name, parentId, etc.)."""
    values = body.model_dump(exclude_none=True)
    # Merge camelCase parentId → parent_id
    if "parentId" in values:
        values["parent_id"] = values.pop("parentId")
    if not values:
        return {"ok": True}
    if "metadata" in values:
        values["metadata_"] = values.pop("metadata")
    values["updated_at"] = _now()
    await session.execute(
        update(File)
        .where(and_(File.id == file_id, File.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.post("/check-hash")
async def check_file_hash(
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Check if a file with the given hash already exists for this user."""
    file_hash = body.get("hash", "")
    if not file_hash:
        return {"isExist": False}
    stmt = select(File).where(and_(File.file_hash == file_hash, File.user_id == user_id)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return {
            "file": _file_dict(row),
            "fileType": row.file_type,
            "isExist": True,
            "metadata": row.metadata_,
            "size": row.size,
            "url": row.url,
        }
    return {"isExist": False}


@router.post("/batch-delete")
async def remove_files(
    body: BatchDeleteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete multiple files by IDs."""
    if not body.ids:
        return {"ok": True}
    # Get files for S3 cleanup
    stmt = select(File).where(and_(File.id.in_(body.ids), File.user_id == user_id))
    files = (await session.execute(stmt)).scalars().all()
    urls = [f.url for f in files if f.url]
    # Delete DB records
    await session.execute(
        delete(File).where(and_(File.id.in_(body.ids), File.user_id == user_id))
    )
    # Best-effort S3 cleanup
    if urls:
        try:
            s3 = S3Client.from_settings()
            for url in urls:
                try:
                    s3.delete_file(url)
                except Exception:
                    pass
        except Exception:
            pass
    return {"ok": True, "count": len(files)}


@router.delete("")
async def remove_all_files(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all files for the user."""
    stmt = select(File).where(File.user_id == user_id)
    files = (await session.execute(stmt)).scalars().all()
    urls = [f.url for f in files if f.url]
    await session.execute(delete(File).where(File.user_id == user_id))
    if urls:
        try:
            s3 = S3Client.from_settings()
            for url in urls:
                try:
                    s3.delete_file(url)
                except Exception:
                    pass
        except Exception:
            pass
    return {"ok": True}


@router.get("/recent")
async def recent_files(
    limit: int = 12,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Return recently accessed/created files."""
    stmt = (
        select(File)
        .where(File.user_id == user_id)
        .order_by(desc(File.accessed_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_file_dict(r) for r in rows]


@router.get("/recent-pages")
async def recent_pages(
    limit: int = 12,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Return recently accessed documents (pages)."""
    stmt = (
        select(Document)
        .where(
            and_(
                Document.user_id == user_id,
                Document.source_type == "document",
                Document.file_type != "custom/folder",
            )
        )
        .order_by(desc(Document.accessed_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "file_type": d.file_type,
            "source_type": d.source_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in rows
    ]


@router.get("/knowledge-items")
async def get_knowledge_items(
    knowledge_base_id: Optional[str] = None,
    category: Optional[str] = None,
    file_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Return knowledge items (files + documents joined)."""
    # Query files
    file_stmt = select(File).where(File.user_id == user_id)
    if knowledge_base_id:
        file_stmt = file_stmt.where(File.parent_id.isnot(None))
    if file_type:
        file_stmt = file_stmt.where(File.file_type == file_type)
    if q:
        file_stmt = file_stmt.where(File.name.ilike(f"%{q}%"))
    file_stmt = file_stmt.order_by(desc(File.created_at)).offset(offset).limit(limit)
    file_rows = (await session.execute(file_stmt)).scalars().all()

    result = [_file_dict(r) for r in file_rows]
    await _attach_file_statuses(session, user_id, result, file_rows)
    has_more = len(result) >= limit
    return {"items": result, "has_more": has_more, "total": len(result)}


@router.get("/{file_id}/item")
async def get_file_item_by_id_alias(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /{file_id}/item — frontend expects this path."""
    return await get_file_item_by_id(file_id, user_id=user_id, session=session)


@router.get("/item/{file_id}")
async def get_file_item_by_id(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get a single file item with status info."""
    f = await get_file_by_id(session, user_id, file_id)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    item = _file_dict(f)
    await _attach_file_statuses(session, user_id, [item], [f])
    return item


@router.delete("/{file_id}/async-task")
async def remove_file_async_task(
    file_id: str,
    type: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove a chunking or embedding async task from a file."""
    task_type = type or "chunk"
    f = await get_file_by_id(session, user_id, file_id)
    if not f:
        return {"ok": True}
    task_id = f.chunk_task_id if task_type == "chunk" else f.embedding_task_id
    col = "chunk_task_id" if task_type == "chunk" else "embedding_task_id"
    await session.execute(
        update(File).where(File.id == file_id).values(**{col: None})
    )
    if task_id:
        await session.execute(delete(AsyncTask).where(AsyncTask.id == task_id))
    return {"ok": True}


# ── Missing TS parity endpoints ────────────────────────────────────


class QueryFileListBody(BaseModel):
    knowledge_base_id: Optional[str] = None
    category: Optional[str] = None
    file_type: Optional[str] = None
    q: Optional[str] = None


@router.post("/knowledge-item-statuses")
async def get_knowledge_item_statuses_alias(
    body: dict[str, list[str]],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /knowledge-item-statuses — frontend expects this path."""
    return await get_knowledge_item_statuses_by_ids(body, user_id=user_id, session=session)


@router.post("/knowledge-items/statuses")
async def get_knowledge_item_statuses_by_ids(
    body: dict[str, list[str]],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get statuses for knowledge items by their IDs."""
    ids = list(set(body.get("ids", [])))
    if not ids:
        return []

    file_stmt = select(File).where(and_(File.id.in_(ids), File.user_id == user_id))
    files = (await session.execute(file_stmt)).scalars().all()
    file_map = {f.id: f for f in files}
    status_items = [_file_dict(f) for f in files]
    await _attach_file_statuses(session, user_id, status_items, files)
    status_by_id = {item["id"]: item for item in status_items}

    results = []
    for fid in ids:
        f = file_map.get(fid)
        if not f:
            continue
        status_item = status_by_id.get(fid, {})
        results.append({
            "id": fid,
            "chunkingStatus": status_item.get("chunking_status"),
            "embeddingStatus": status_item.get("embedding_status"),
        })
    return results


@router.get("/knowledge-item-ids")
async def resolve_knowledge_item_ids_get(
    knowledge_base_id: Optional[str] = None,
    knowledgeBaseId: Optional[str] = None,
    category: Optional[str] = None,
    file_type: Optional[str] = None,
    fileType: Optional[str] = None,
    q: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /knowledge-item-ids — frontend expects this path and GET method."""
    body = QueryFileListBody(
        knowledge_base_id=knowledgeBaseId or knowledge_base_id,
        category=category,
        file_type=fileType or file_type,
        q=q,
    )
    return await resolve_knowledge_item_ids(body, user_id=user_id, session=session)


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


@router.post("/knowledge-items/resolve-ids")
async def resolve_knowledge_item_ids(
    body: QueryFileListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Resolve all knowledge item IDs matching a query (paginated internally)."""
    ids: list[str] = []
    batch_size = 500
    offset = 0

    while True:
        stmt = select(File.id).where(File.user_id == user_id)
        if body.knowledge_base_id:
            stmt = stmt.where(File.parent_id.isnot(None))
        if body.file_type:
            stmt = stmt.where(File.file_type == body.file_type)
        if body.q:
            stmt = stmt.where(File.name.ilike(f"%{body.q}%"))
        stmt = stmt.offset(offset).limit(batch_size + 1)

        rows = (await session.execute(stmt)).scalars().all()
        has_more = len(rows) > batch_size
        batch = rows[:batch_size] if has_more else rows
        ids.extend(batch)
        offset += len(batch)
        if not has_more:
            break

    return {"ids": ids, "total": len(ids)}


@router.post("/knowledge-items/delete")
async def delete_knowledge_items_alias(
    body: QueryFileListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /knowledge-items/delete — frontend expects this path."""
    return await delete_knowledge_items_by_query(body, user_id=user_id, session=session)


@router.post("/knowledge-items/delete-by-query")
async def delete_knowledge_items_by_query(
    body: QueryFileListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all knowledge items matching a query."""
    file_ids: list[str] = []
    document_ids: list[str] = []
    batch_size = 500
    offset = 0

    while True:
        stmt = select(File).where(File.user_id == user_id)
        if body.knowledge_base_id:
            stmt = stmt.where(File.parent_id.isnot(None))
        if body.file_type:
            stmt = stmt.where(File.file_type == body.file_type)
        if body.q:
            stmt = stmt.where(File.name.ilike(f"%{body.q}%"))
        stmt = stmt.offset(offset).limit(batch_size + 1)

        rows = (await session.execute(stmt)).scalars().all()
        has_more = len(rows) > batch_size
        batch = rows[:batch_size] if has_more else rows
        for f in batch:
            file_ids.append(f.id)
        offset += len(batch)
        if not has_more:
            break

    count = 0
    if file_ids:
        # Get URLs for S3 cleanup
        files_to_delete = (await session.execute(
            select(File).where(and_(File.id.in_(file_ids), File.user_id == user_id))
        )).scalars().all()
        urls = [f.url for f in files_to_delete if f.url]

        await session.execute(
            delete(File).where(and_(File.id.in_(file_ids), File.user_id == user_id))
        )
        count = len(file_ids)

        # Best-effort S3 cleanup
        if urls:
            try:
                s3 = S3Client.from_settings()
                for url in urls:
                    try:
                        s3.delete_file(url)
                    except Exception:
                        pass
            except Exception:
                pass

    return {"count": count}


# ── Helpers ──────────────────────────────────────────────────────────

async def _attach_file_statuses(
    session: AsyncSession,
    user_id: str,
    items: list[dict[str, Any]],
    files: list[File],
) -> None:
    if not items:
        return

    task_ids = {
        task_id
        for f in files
        for task_id in (f.chunk_task_id, f.embedding_task_id)
        if task_id
    }
    tasks: dict[str, AsyncTask] = {}
    if task_ids:
        rows = (
            await session.execute(
                select(AsyncTask).where(
                    and_(AsyncTask.user_id == user_id, AsyncTask.id.in_(task_ids))
                )
            )
        ).scalars().all()
        tasks = {t.id: t for t in rows}

    file_ids = [f.id for f in files]
    chunk_counts: dict[str, int] = {}
    if file_ids:
        rows = (
            await session.execute(
                select(Document.file_id, func.count(DocumentChunk.chunk_id))
                .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                .where(
                    and_(Document.user_id == user_id, Document.file_id.in_(file_ids))
                )
                .group_by(Document.file_id)
            )
        ).all()
        chunk_counts = {file_id: count for file_id, count in rows if file_id}

    files_by_id = {f.id: f for f in files}
    for item in items:
        file = files_by_id.get(item["id"])
        if not file:
            continue

        chunk_task = tasks.get(file.chunk_task_id) if file.chunk_task_id else None
        embedding_task = tasks.get(file.embedding_task_id) if file.embedding_task_id else None
        item["chunking_status"] = chunk_task.status if chunk_task else None
        item["embedding_status"] = embedding_task.status if embedding_task else None
        item["chunk_count"] = chunk_counts.get(file.id, 0)


def _file_dict(f: File) -> dict[str, Any]:
    return {
        "id": f.id,
        "name": f.name,
        "url": f"/f/{f.id}",
        "file_type": f.file_type,
        "size": f.size,
        "file_hash": f.file_hash,
        "source": f.source,
        "parent_id": f.parent_id,
        "chunk_task_id": f.chunk_task_id,
        "embedding_task_id": f.embedding_task_id,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }
