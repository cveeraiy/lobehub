"""Chunk router — chunk-level CRUD and search within a document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.rag import Chunk, DocumentChunk, Embedding
from app.models.file import Document, File
from app.models.knowledge import KnowledgeBaseFile
from app.models.misc import AsyncTask

router = APIRouter(prefix="/api/chunks", tags=["Chunks"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateChunkBody(BaseModel):
    text: Optional[str] = None
    abstract: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SearchChunksBody(BaseModel):
    query: str
    knowledge_base_id: Optional[str] = None
    document_id: Optional[str] = None
    limit: int = 10


class BatchDeleteChunksBody(BaseModel):
    ids: list[str]


class CreateParseFileTaskBody(BaseModel):
    id: str
    skip_exist: Optional[bool] = False


class CreateEmbeddingChunksTaskBody(BaseModel):
    id: str


class GetFileContentsBody(BaseModel):
    file_ids: list[str]


class SemanticSearchForChatBody(BaseModel):
    query: str
    file_ids: Optional[list[str]] = None
    knowledge_ids: Optional[list[str]] = None
    top_k: Optional[int] = 15


# ── Frontend path aliases ─────────────────────────────────────────────
# Frontend sends to these paths; they delegate to the canonical handlers.

@router.post("/parse-file-task")
async def parse_file_task_alias(
    body: CreateParseFileTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /parse-file-task — frontend path."""
    return await create_parse_file_task(body, user_id=user_id, session=session)


@router.post("/retry-parse")
async def retry_parse_alias(
    body: CreateParseFileTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /retry-parse — frontend path."""
    return await retry_parse_file_task(body, user_id=user_id, session=session)


@router.post("/embedding-task")
async def embedding_task_alias(
    body: CreateEmbeddingChunksTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /embedding-task — frontend path."""
    return await create_embedding_chunks_task(body, user_id=user_id, session=session)


@router.post("/semantic-search")
async def semantic_search_alias(
    body: SearchChunksBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /semantic-search — frontend path."""
    return await search_chunks(body, user_id=user_id, session=session)


@router.post("/semantic-search-chat")
async def semantic_search_chat_alias(
    body: SemanticSearchForChatBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /semantic-search-chat — frontend path."""
    return await semantic_search_for_chat(body, user_id=user_id, session=session)


@router.post("/file-contents")
async def file_contents_alias(
    body: GetFileContentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /file-contents — frontend path."""
    return await get_file_contents(body, user_id=user_id, session=session)


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/create-parse-task")
async def create_parse_file_task(
    body: CreateParseFileTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create an async task to parse a file into chunks."""
    task = AsyncTask(
        user_id=user_id,
        type="chunk",
        status="pending",
    )
    session.add(task)
    await session.flush()
    # Update the file's chunk task id
    await session.execute(
        update(File)
        .where(and_(File.id == body.id, File.user_id == user_id))
        .values(chunk_task_id=task.id)
    )
    return {"id": task.id, "success": True}


@router.post("/retry-parse-task")
async def retry_parse_file_task(
    body: CreateParseFileTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Retry parsing a file by deleting old task and creating new one."""
    file = (await session.execute(
        select(File).where(and_(File.id == body.id, File.user_id == user_id))
    )).scalar_one_or_none()
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    # Delete old task if exists
    if file.chunk_task_id:
        await session.execute(
            delete(AsyncTask).where(AsyncTask.id == file.chunk_task_id)
        )

    # Create new task
    task = AsyncTask(user_id=user_id, type="chunk", status="pending")
    session.add(task)
    await session.flush()
    await session.execute(
        update(File)
        .where(and_(File.id == body.id, File.user_id == user_id))
        .values(chunk_task_id=task.id)
    )
    return {"id": task.id, "success": True}


@router.post("/create-embedding-task")
async def create_embedding_chunks_task(
    body: CreateEmbeddingChunksTaskBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create an async task to embed file chunks."""
    task = AsyncTask(
        user_id=user_id,
        type="embedding",
        status="pending",
    )
    session.add(task)
    await session.flush()
    # Update the file's embedding task id
    await session.execute(
        update(File)
        .where(and_(File.id == body.id, File.user_id == user_id))
        .values(embedding_task_id=task.id)
    )
    return {"id": task.id, "success": True}


@router.get("/by-file/{file_id}")
async def get_chunks_by_file_id(
    file_id: str,
    cursor: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get chunks belonging to a file (via its document)."""
    doc = (await session.execute(
        select(Document).where(
            and_(Document.file_id == file_id, Document.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not doc:
        return {"items": [], "nextCursor": cursor}

    stmt = (
        select(Chunk)
        .join(DocumentChunk, DocumentChunk.chunk_id == Chunk.id)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(Chunk.index)
        .offset(cursor * 100)
        .limit(100)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [_chunk_dict(c) for c in rows],
        "nextCursor": cursor + 1 if rows else cursor,
    }


@router.post("/get-file-contents")
async def get_file_contents(
    body: GetFileContentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get file contents for multiple files."""
    results = []
    for file_id in body.file_ids:
        file = (await session.execute(
            select(File).where(and_(File.id == file_id, File.user_id == user_id))
        )).scalar_one_or_none()
        if not file:
            results.append({"fileId": file_id, "filename": f"Unknown file {file_id}", "content": "", "error": "File not found"})
            continue

        doc = (await session.execute(
            select(Document).where(
                and_(Document.file_id == file_id, Document.user_id == user_id)
            )
        )).scalar_one_or_none()

        content = doc.content or "" if doc else ""
        lines = content.split("\n")
        results.append({
            "fileId": file_id,
            "filename": file.name,
            "content": content,
            "metadata": doc.metadata_ if doc else None,
            "preview": "\n".join(lines[:5]),
            "totalCharCount": len(content),
            "totalLineCount": len(lines),
        })
    return results


@router.post("/semantic-search-for-chat")
async def semantic_search_for_chat(
    body: SemanticSearchForChatBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Semantic search for chat with file grouping (placeholder — needs embedding service)."""
    from app.services import knowledge_service, llm_service

    try:
        query = body.query[:8000] if len(body.query) > 8000 else body.query
        vectors = await llm_service.embed([query])
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Embedding failed: {exc}")

    # Collect file IDs from explicit list + knowledge bases
    file_ids = list(body.file_ids or [])
    if body.knowledge_ids:
        kb_file_ids = (await session.execute(
            select(KnowledgeBaseFile.file_id).where(
                KnowledgeBaseFile.knowledge_base_id.in_(body.knowledge_ids)
            )
        )).scalars().all()
        file_ids.extend(kb_file_ids)

    results = await knowledge_service.vector_search(
        session, user_id, vectors[0],
        file_ids=file_ids if file_ids else None,
        limit=body.top_k or 15,
    )
    return {"chunks": results, "fileResults": []}


@router.get("/count")
async def count_chunks(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    count = (await session.execute(
        select(func.count()).select_from(Chunk).where(Chunk.user_id == user_id)
    )).scalar_one()
    return {"count": count}


@router.get("/by-knowledge-base/{kb_id}")
async def list_chunks_by_knowledge_base(
    kb_id: str,
    limit: int = 100,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Get documents in this KB, then their chunks
    doc_ids = (await session.execute(
        select(Document.id)
        .join(KnowledgeBaseFile, KnowledgeBaseFile.file_id == Document.id)
        .where(KnowledgeBaseFile.knowledge_base_id == kb_id)
    )).scalars().all()
    if not doc_ids:
        return []
    stmt = (
        select(Chunk)
        .join(DocumentChunk, DocumentChunk.chunk_id == Chunk.id)
        .where(DocumentChunk.document_id.in_(doc_ids))
        .order_by(Chunk.index)
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_chunk_dict(c) for c in rows]


@router.post("/batch-delete")
async def batch_delete_chunks(
    body: BatchDeleteChunksBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.ids:
        await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(body.ids)))
        await session.execute(
            delete(Chunk).where(and_(Chunk.id.in_(body.ids), Chunk.user_id == user_id))
        )
    return {"ok": True}


@router.post("/search")
async def search_chunks(
    body: SearchChunksBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Vector search across chunks (requires embedding the query first)."""
    from app.services import knowledge_service, llm_service

    try:
        vectors = await llm_service.embed([body.query])
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Embedding failed: {exc}")

    results = await knowledge_service.vector_search(
        session,
        user_id,
        vectors[0],
        kb_id=body.knowledge_base_id,
        limit=body.limit,
    )
    return results


@router.get("/{chunk_id}")
async def get_chunk(
    chunk_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    chunk = await _find_chunk(session, user_id, chunk_id)
    if not chunk:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    return _chunk_dict(chunk)


@router.put("/{chunk_id}")
async def update_chunk(
    chunk_id: str,
    body: UpdateChunkBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update chunk text/abstract (e.g. after manual correction)."""
    values: dict[str, Any] = {}
    if body.text is not None:
        values["text"] = body.text
    if body.abstract is not None:
        values["abstract"] = body.abstract
    if body.metadata is not None:
        values["metadata_"] = body.metadata
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    stmt = (
        update(Chunk)
        .where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{chunk_id}")
async def delete_chunk(
    chunk_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a chunk and its embedding."""
    await session.execute(delete(Embedding).where(Embedding.chunk_id == chunk_id))
    await session.execute(
        delete(Chunk).where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_chunk(db: AsyncSession, user_id: str, chunk_id: str) -> Chunk | None:
    stmt = select(Chunk).where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _chunk_dict(c: Chunk) -> dict[str, Any]:
    return {
        "id": c.id,
        "text": c.text,
        "abstract": c.abstract,
        "index": c.index,
        "type": c.type,
        "metadata": c.metadata_,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
