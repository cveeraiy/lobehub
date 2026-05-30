"""Knowledge-base service — CRUD, chunking, embedding, vector search.

Manages ``knowledge_bases``, ``knowledge_base_files``, ``chunks``,
``embeddings``, and ``document_chunks`` tables.
"""

from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentKnowledgeBase
from app.models.file import Document, File
from app.models.knowledge import KnowledgeBase, KnowledgeBaseFile
from app.models.misc import AsyncTask
from app.models.rag import Chunk, DocumentChunk, Embedding
from app.models.rag_eval import (
    RagEvalDataset,
    RagEvalDatasetRecord,
    RagEvalEvaluation,
    RagEvalEvaluationRecord,
)
from app.services import llm_service

logger = logging.getLogger(__name__)

PROCESSING_STATUSES = {"pending", "processing"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
#  Knowledge Base CRUD
# ─────────────────────────────────────────────────────────────────────

async def create_knowledge_base(
    session: AsyncSession,
    user_id: str,
    *,
    name: str,
    description: Optional[str] = None,
    avatar: Optional[str] = None,
    kb_type: Optional[str] = None,
    settings: Optional[dict[str, Any]] = None,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description=description,
        avatar=avatar,
        type=kb_type,
        user_id=user_id,
        settings=settings,
    )
    session.add(kb)
    await session.flush()
    return kb


async def get_knowledge_base(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
) -> KnowledgeBase | None:
    stmt = select(KnowledgeBase).where(
        and_(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_knowledge_bases(
    session: AsyncSession,
    user_id: str,
) -> list[KnowledgeBase]:
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_knowledge_base_processing_statuses(
    session: AsyncSession,
    user_id: str,
    kb_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Aggregate file processing state for each knowledge base."""
    if not kb_ids:
        return {}

    file_rows = (
        await session.execute(
            select(
                KnowledgeBaseFile.knowledge_base_id,
                File.id,
                File.chunk_task_id,
                File.embedding_task_id,
            )
            .join(File, File.id == KnowledgeBaseFile.file_id)
            .where(
                and_(
                    KnowledgeBaseFile.knowledge_base_id.in_(kb_ids),
                    KnowledgeBaseFile.user_id == user_id,
                    File.user_id == user_id,
                )
            )
        )
    ).all()

    file_ids = [row.id for row in file_rows]
    task_ids = {
        task_id
        for row in file_rows
        for task_id in (row.chunk_task_id, row.embedding_task_id)
        if task_id
    }

    tasks: dict[str, AsyncTask] = {}
    if task_ids:
        task_rows = (
            await session.execute(
                select(AsyncTask).where(
                    and_(AsyncTask.id.in_(task_ids), AsyncTask.user_id == user_id)
                )
            )
        ).scalars().all()
        tasks = {task.id: task for task in task_rows}

    chunk_counts: dict[str, int] = {}
    embedded_counts: dict[str, int] = {}
    if file_ids:
        chunk_rows = (
            await session.execute(
                select(Document.file_id, func.count(DocumentChunk.chunk_id))
                .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                .where(
                    and_(
                        Document.user_id == user_id,
                        Document.file_id.in_(file_ids),
                        DocumentChunk.user_id == user_id,
                    )
                )
                .group_by(Document.file_id)
            )
        ).all()
        chunk_counts = {row.file_id: int(row[1] or 0) for row in chunk_rows if row.file_id}

        embedded_rows = (
            await session.execute(
                select(Document.file_id, func.count(Embedding.id))
                .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                .join(Embedding, Embedding.chunk_id == DocumentChunk.chunk_id)
                .where(
                    and_(
                        Document.user_id == user_id,
                        Document.file_id.in_(file_ids),
                        DocumentChunk.user_id == user_id,
                        Embedding.user_id == user_id,
                    )
                )
                .group_by(Document.file_id)
            )
        ).all()
        embedded_counts = {row.file_id: int(row[1] or 0) for row in embedded_rows if row.file_id}

    grouped: dict[str, list[Any]] = {kb_id: [] for kb_id in kb_ids}
    for row in file_rows:
        grouped.setdefault(row.knowledge_base_id, []).append(row)

    summaries: dict[str, dict[str, Any]] = {}
    for kb_id, rows in grouped.items():
        file_count = len(rows)
        total_chunks = sum(chunk_counts.get(row.id, 0) for row in rows)
        total_embeddings = sum(embedded_counts.get(row.id, 0) for row in rows)

        chunk_tasks = [tasks[row.chunk_task_id] for row in rows if row.chunk_task_id in tasks]
        embedding_tasks = [
            tasks[row.embedding_task_id] for row in rows if row.embedding_task_id in tasks
        ]

        chunking_status: str | None = None
        chunking_error: dict[str, Any] | None = None
        if file_count:
            errored_task = next((task for task in chunk_tasks if task.status == "error"), None)
            if errored_task:
                chunking_status = "error"
                chunking_error = errored_task.error
            elif any(task.status in PROCESSING_STATUSES for task in chunk_tasks):
                chunking_status = "processing"
            elif total_chunks > 0 and len(chunk_tasks) == file_count:
                chunking_status = "success"
            elif total_chunks > 0 or chunk_tasks:
                chunking_status = "processing"

        embedding_status: str | None = None
        embedding_error: dict[str, Any] | None = None
        if total_chunks > 0:
            errored_embedding = next(
                (task for task in embedding_tasks if task.status == "error"), None
            )
            if errored_embedding:
                embedding_status = "error"
                embedding_error = errored_embedding.error
            elif total_embeddings >= total_chunks:
                embedding_status = "success"
            elif any(task.status in PROCESSING_STATUSES for task in embedding_tasks):
                embedding_status = "processing"
            elif embedding_tasks:
                embedding_status = "processing"

        summaries[kb_id] = {
            "chunk_count": total_chunks,
            "chunking_error": chunking_error,
            "chunking_status": chunking_status,
            "embedding_count": total_embeddings,
            "embedding_error": embedding_error,
            "embedding_status": embedding_status,
            "file_count": file_count,
            "finish_embedding": embedding_status == "success",
        }

    return summaries


async def update_knowledge_base(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    **values: Any,
) -> None:
    values["updated_at"] = _now()
    stmt = (
        update(KnowledgeBase)
        .where(and_(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)


async def delete_knowledge_base(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
) -> None:
    await session.execute(
        update(Document)
        .where(and_(Document.knowledge_base_id == kb_id, Document.user_id == user_id))
        .values(knowledge_base_id=None, updated_at=_now())
    )
    await session.execute(
        delete(AgentKnowledgeBase).where(
            and_(
                AgentKnowledgeBase.knowledge_base_id == kb_id,
                AgentKnowledgeBase.user_id == user_id,
            )
        )
    )
    dataset_ids = (
        await session.execute(
            select(RagEvalDataset.id).where(
                and_(
                    RagEvalDataset.knowledge_base_id == kb_id,
                    RagEvalDataset.user_id == user_id,
                )
            )
        )
    ).scalars().all()
    evaluation_ids = (
        await session.execute(
            select(RagEvalEvaluation.id).where(
                and_(
                    RagEvalEvaluation.knowledge_base_id == kb_id,
                    RagEvalEvaluation.user_id == user_id,
                )
            )
        )
    ).scalars().all()
    if evaluation_ids:
        await session.execute(
            delete(RagEvalEvaluationRecord).where(
                RagEvalEvaluationRecord.evaluation_id.in_(evaluation_ids)
            )
        )
    await session.execute(
        delete(RagEvalEvaluation).where(
            and_(
                RagEvalEvaluation.knowledge_base_id == kb_id,
                RagEvalEvaluation.user_id == user_id,
            )
        )
    )
    if dataset_ids:
        await session.execute(
            delete(RagEvalDatasetRecord).where(
                RagEvalDatasetRecord.dataset_id.in_(dataset_ids)
            )
        )
    await session.execute(
        delete(RagEvalDataset).where(
            and_(
                RagEvalDataset.knowledge_base_id == kb_id,
                RagEvalDataset.user_id == user_id,
            )
        )
    )
    # Remove junction records
    await session.execute(
        delete(KnowledgeBaseFile).where(
            and_(KnowledgeBaseFile.knowledge_base_id == kb_id,
                 KnowledgeBaseFile.user_id == user_id)
        )
    )
    await session.execute(
        delete(KnowledgeBase).where(
            and_(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
        )
    )


async def delete_all_knowledge_bases(
    session: AsyncSession,
    user_id: str,
) -> None:
    await session.execute(
        delete(KnowledgeBaseFile).where(KnowledgeBaseFile.user_id == user_id)
    )
    await session.execute(
        delete(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
    )


# ─────────────────────────────────────────────────────────────────────
#  Knowledge Base ↔ File association
# ─────────────────────────────────────────────────────────────────────

async def add_file_to_kb(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    file_id: str,
) -> None:
    link = KnowledgeBaseFile(
        knowledge_base_id=kb_id,
        file_id=file_id,
        user_id=user_id,
    )
    session.add(link)
    await session.flush()


async def remove_file_from_kb(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    file_id: str,
) -> None:
    await session.execute(
        delete(KnowledgeBaseFile).where(
            and_(
                KnowledgeBaseFile.knowledge_base_id == kb_id,
                KnowledgeBaseFile.file_id == file_id,
                KnowledgeBaseFile.user_id == user_id,
            )
        )
    )


async def list_kb_files(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
) -> list[dict[str, Any]]:
    """Return files in a knowledge base with basic metadata."""
    stmt = (
        select(File.id, File.name, File.file_type, File.size, File.created_at)
        .join(KnowledgeBaseFile, KnowledgeBaseFile.file_id == File.id)
        .where(
            and_(
                KnowledgeBaseFile.knowledge_base_id == kb_id,
                KnowledgeBaseFile.user_id == user_id,
            )
        )
        .order_by(File.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [dict(r._mapping) for r in rows]


# ─────────────────────────────────────────────────────────────────────
#  Chunking
# ─────────────────────────────────────────────────────────────────────

async def create_chunks(
    session: AsyncSession,
    user_id: str,
    texts: list[str],
    *,
    document_id: Optional[str] = None,
    chunk_type: str = "text",
    metadata: Optional[dict[str, Any]] = None,
) -> list[Chunk]:
    """Create chunk records from text segments."""
    chunks: list[Chunk] = []
    for i, text in enumerate(texts):
        chunk = Chunk(
            id=str(_uuid.uuid4()),
            text=text,
            index=i,
            type=chunk_type,
            user_id=user_id,
            metadata_=metadata,
        )
        session.add(chunk)
        chunks.append(chunk)

    await session.flush()

    # Link to document if provided
    if document_id:
        for i, chunk in enumerate(chunks):
            link = DocumentChunk(
                document_id=document_id,
                chunk_id=chunk.id,
                page_index=i,
                user_id=user_id,
            )
            session.add(link)
        await session.flush()

    return chunks


# ─────────────────────────────────────────────────────────────────────
#  Embedding
# ─────────────────────────────────────────────────────────────────────

async def embed_chunks(
    session: AsyncSession,
    user_id: str,
    chunks: list[Chunk],
    *,
    model: str = "openai/text-embedding-3-small",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    batch_size: int = 50,
) -> list[Embedding]:
    """Embed a list of chunks and store vectors in ``embeddings``."""
    from app.config import settings as cfg

    bs = cfg.embedding_batch_size or batch_size
    concurrency = cfg.embedding_concurrency or 10
    sem = asyncio.Semaphore(concurrency)
    all_embeddings: list[Embedding] = []

    async def _embed_batch(batch: list[Chunk]) -> list[tuple[Chunk, list[float]]]:
        async with sem:
            texts = [c.text or "" for c in batch]
            vectors = await llm_service.embed(
                texts, model=model, api_key=api_key, api_base=api_base
            )
            return list(zip(batch, vectors))

    tasks = [
        _embed_batch(chunks[start : start + bs])
        for start in range(0, len(chunks), bs)
    ]
    batch_results = await asyncio.gather(*tasks)

    for pairs in batch_results:
        for chunk, vec in pairs:
            emb = Embedding(
                id=str(_uuid.uuid4()),
                chunk_id=chunk.id,
                embeddings=vec,
                model=model,
                user_id=user_id,
            )
            session.add(emb)
            all_embeddings.append(emb)

    await session.flush()
    return all_embeddings


# ─────────────────────────────────────────────────────────────────────
#  Vector search
# ─────────────────────────────────────────────────────────────────────

async def vector_search(
    session: AsyncSession,
    user_id: str,
    query_vector: list[float],
    *,
    limit: int = 10,
    kb_id: Optional[str] = None,
    file_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Search chunks by vector similarity (cosine distance via pgvector).

    Optionally filter by knowledge base or specific file IDs.
    """
    from sqlalchemy import literal_column

    # Build distance expression using a proper vector literal (avoids SQL text bloat)
    vec_literal = literal_column(f"'{query_vector}'::vector")
    distance = Embedding.embeddings.op("<=>")(vec_literal)

    stmt = (
        select(
            Chunk.id,
            Chunk.text,
            Chunk.metadata_,
            Chunk.index,
            Document.id.label("document_id"),
            Document.file_id,
            Document.title.label("document_title"),
            Document.filename.label("document_filename"),
            File.name.label("file_name"),
            distance.label("distance"),
        )
        .join(Embedding, Embedding.chunk_id == Chunk.id)
        .join(DocumentChunk, DocumentChunk.chunk_id == Chunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(File, File.id == Document.file_id)
        .where(Chunk.user_id == user_id)
        .order_by(distance)
        .limit(limit)
    )

    # Filter by KB → files in that KB
    if kb_id:
        file_subq = (
            select(KnowledgeBaseFile.file_id)
            .where(
                and_(
                    KnowledgeBaseFile.knowledge_base_id == kb_id,
                    KnowledgeBaseFile.user_id == user_id,
                )
            )
        )
        doc_subq = (
            select(DocumentChunk.chunk_id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(or_(Document.knowledge_base_id == kb_id, Document.file_id.in_(file_subq)))
        )
        stmt = stmt.where(Chunk.id.in_(doc_subq))

    if file_ids:
        doc_subq2 = (
            select(DocumentChunk.chunk_id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(or_(DocumentChunk.document_id.in_(file_ids), Document.file_id.in_(file_ids)))
        )
        stmt = stmt.where(Chunk.id.in_(doc_subq2))

    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "text": r.text,
            "metadata": r.metadata_,
            "index": r.index,
            "distance": float(r.distance),
            "similarity": max(0.0, 1.0 - float(r.distance)),
            "documentId": r.document_id,
            "fileId": r.file_id or r.document_id,
            "fileName": r.file_name or r.document_title or r.document_filename or "Untitled",
        }
        for r in rows
    ]
