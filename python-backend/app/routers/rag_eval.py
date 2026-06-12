"""RAG Evaluation router — datasets, records, evaluations, and evaluation execution.

Covers TS parity for: createDataset, getDatasets, removeDataset, updateDataset,
createDatasetRecords, getDatasetRecords, removeDatasetRecords, updateDatasetRecords,
importDatasetRecords, createEvaluation, getEvaluationList, removeEvaluation,
startEvaluationTask, checkEvaluationStatus.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pydantic import Field as PField
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models._helpers import create_nanoid
from app.services.file_service import S3Client
from app.services.rag_parsing import lexical_search_chunks

router = APIRouter(prefix="/api/rag-eval", tags=["RAG Evaluation"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _score_answer(answer: str, ideal: str | None) -> tuple[float, bool, str]:
    if not ideal:
        return 1.0, True, "No ideal answer configured."
    answer_terms = {term for term in re.findall(r"\w+", answer.lower()) if len(term) > 1}
    ideal_terms = {term for term in re.findall(r"\w+", ideal.lower()) if len(term) > 1}
    if not ideal_terms:
        return 1.0, True, "Ideal answer is empty."
    overlap = len(answer_terms & ideal_terms)
    score = overlap / len(ideal_terms)
    return score, score >= 0.6, f"Matched {overlap}/{len(ideal_terms)} ideal terms."


def _parse_import_records_content(content: str) -> list[dict[str, Any]]:
    stripped = content.strip()
    if not stripped:
        return []

    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("Dataset import JSON must be an array")
        return [item for item in parsed if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    for line in stripped.splitlines():
        value = line.strip()
        if not value:
            continue
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Dataset import JSONL rows must be objects")
        records.append(parsed)
    return records


def _coerce_reference_file_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


async def _resolve_reference_file_ids(
    reference_files: Any,
    *,
    user_id: str,
    session: AsyncSession,
) -> list[str] | None:
    names = _coerce_reference_file_names(reference_files)
    if not names:
        return None

    rows = (
        await session.execute(
            text("SELECT id FROM files WHERE user_id = :uid AND name = ANY(:names)"),
            {"names": names, "uid": user_id},
        )
    ).fetchall()
    return [row[0] for row in rows]


async def _insert_dataset_import_records(
    dataset_id: str,
    records: list[dict[str, Any]],
    *,
    user_id: str,
    session: AsyncSession,
) -> int:
    count = 0
    for rec in records:
        rec_id = create_nanoid(32)
        reference_files = await _resolve_reference_file_ids(
            rec.get("referenceFiles") or rec.get("reference_files"),
            user_id=user_id,
            session=session,
        )
        await session.execute(
            text(
                "INSERT INTO rag_eval_dataset_records (id, dataset_id, question, ideal, reference_files, user_id) "
                "VALUES (:id, :ds_id, :question, :ideal, :ref_files, :uid)"
            ),
            {
                "id": rec_id,
                "ds_id": dataset_id,
                "question": rec.get("question", ""),
                "ideal": rec.get("ideal"),
                "ref_files": reference_files,
                "uid": user_id,
            },
        )
        count += 1
    return count


# ── Schemas ──────────────────────────────────────────────────────────


class CreateDatasetBody(BaseModel):
    model_config = {"populate_by_name": True}
    name: str
    description: Optional[str] = None
    knowledge_base_id: str = PField(alias="knowledgeBaseId")


class UpdateDatasetBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CreateDatasetRecordBody(BaseModel):
    model_config = {"populate_by_name": True}
    dataset_id: str = PField(alias="datasetId")
    question: str
    ideal: Optional[str] = None
    reference_files: Optional[list[str]] = PField(default=None, alias="referenceFiles")
    metadata: Optional[dict[str, Any]] = None


class UpdateDatasetRecordBody(BaseModel):
    model_config = {"populate_by_name": True}
    question: Optional[str] = None
    ideal: Optional[str] = None
    reference_files: Optional[list[str]] = PField(default=None, alias="referenceFiles")
    metadata: Optional[dict[str, Any]] = None


class ImportDatasetRecordsBody(BaseModel):
    model_config = {"populate_by_name": True}
    dataset_id: Optional[str] = PField(default=None, alias="datasetId")
    records: Optional[list[dict[str, Any]]] = None
    pathname: Optional[str] = None


class CreateEvaluationBody(BaseModel):
    model_config = {"populate_by_name": True}
    name: str
    description: Optional[str] = None
    knowledge_base_id: str = PField(alias="knowledgeBaseId")
    dataset_id: str = PField(alias="datasetId")


class StartEvaluationBody(BaseModel):
    model_config = {"populate_by_name": True}
    knowledge_base_id: Optional[str] = PField(default=None, alias="knowledgeBaseId")
    file_id: Optional[str] = PField(default=None, alias="fileId")
    dataset: Optional[list[dict[str, Any]]] = None


# ── Dataset CRUD ─────────────────────────────────────────────────────


@router.post("/datasets")
async def create_dataset(
    body: CreateDatasetBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a RAG eval dataset."""
    ds_id = create_nanoid(16)
    await session.execute(
        text(
            "INSERT INTO rag_eval_datasets (id, name, description, knowledge_base_id, user_id) "
            "VALUES (:id, :name, :description, :kb_id, :uid)"
        ),
        {
            "id": ds_id,
            "name": body.name,
            "description": body.description,
            "kb_id": body.knowledge_base_id,
            "uid": user_id,
        },
    )
    return ds_id


@router.get("/datasets")
async def get_datasets(
    knowledge_base_id: str = Query(alias="knowledgeBaseId"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List datasets for a knowledge base."""
    result = await session.execute(
        text(
            "SELECT id, name, description, knowledge_base_id, created_at, updated_at "
            "FROM rag_eval_datasets WHERE knowledge_base_id = :kb_id AND user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"kb_id": knowledge_base_id, "uid": user_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.delete("/datasets/{dataset_id}")
async def remove_dataset(
    dataset_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a dataset and its child records."""
    evaluation_ids = (
        await session.execute(
            text("SELECT id FROM rag_eval_evaluations WHERE dataset_id = :id AND user_id = :uid"),
            {"id": dataset_id, "uid": user_id},
        )
    ).scalars().all()
    if evaluation_ids:
        await session.execute(
            text("DELETE FROM rag_eval_evaluation_records WHERE evaluation_id = ANY(:ids) AND user_id = :uid"),
            {"ids": evaluation_ids, "uid": user_id},
        )
    # Cascade: remove child records first
    await session.execute(
        text("DELETE FROM rag_eval_dataset_records WHERE dataset_id = :id AND user_id = :uid"),
        {"id": dataset_id, "uid": user_id},
    )
    # Also remove evaluations referencing this dataset
    await session.execute(
        text("DELETE FROM rag_eval_evaluations WHERE dataset_id = :id AND user_id = :uid"),
        {"id": dataset_id, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM rag_eval_datasets WHERE id = :id AND user_id = :uid"),
        {"id": dataset_id, "uid": user_id},
    )
    return {"ok": True}


@router.patch("/datasets/{dataset_id}")
@router.put("/datasets/{dataset_id}")
async def update_dataset(
    dataset_id: str,
    body: UpdateDatasetBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a dataset."""
    sets = []
    params: dict[str, Any] = {"id": dataset_id, "uid": user_id}
    if body.name is not None:
        sets.append("name = :name")
        params["name"] = body.name
    if body.description is not None:
        sets.append("description = :description")
        params["description"] = body.description
    if not sets:
        return {"ok": True}
    sets.append("updated_at = now()")
    await session.execute(
        text(f"UPDATE rag_eval_datasets SET {', '.join(sets)} WHERE id = :id AND user_id = :uid"),
        params,
    )
    return {"ok": True}


# ── Dataset Records — nested routes for frontend ────────────────────


@router.get("/datasets/{dataset_id}/records")
async def get_dataset_records_nested(
    dataset_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """GET /rag-eval/datasets/{datasetId}/records — alias used by frontend."""
    result = await session.execute(
        text(
            "SELECT id, dataset_id, question, ideal, reference_files, metadata, created_at "
            "FROM rag_eval_dataset_records WHERE dataset_id = :ds_id AND user_id = :uid "
            "ORDER BY created_at"
        ),
        {"ds_id": dataset_id, "uid": user_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.post("/datasets/{dataset_id}/import")
async def import_dataset_records_nested(
    dataset_id: str,
    body: ImportDatasetRecordsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /rag-eval/datasets/{datasetId}/import — alias used by frontend."""
    effective_ds_id = body.dataset_id or dataset_id
    records = body.records
    if records is None and body.pathname:
        try:
            content = await S3Client.from_settings().get_content(body.pathname)
            records = _parse_import_records_content(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Failed to import dataset records from {body.pathname}",
            ) from exc
    count = await _insert_dataset_import_records(
        effective_ds_id,
        records or [],
        user_id=user_id,
        session=session,
    )
    return {"imported": count}


# ── Dataset Records CRUD ─────────────────────────────────────────────


@router.post("/dataset-records")
async def create_dataset_record(
    body: CreateDatasetRecordBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a dataset record."""
    rec_id = create_nanoid(32)
    await session.execute(
        text(
            "INSERT INTO rag_eval_dataset_records "
            "(id, dataset_id, question, ideal, reference_files, metadata, user_id) "
            "VALUES (:id, :ds_id, :question, :ideal, :ref_files, cast(:meta as json), :uid)"
        ),
        {
            "id": rec_id,
            "ds_id": body.dataset_id,
            "question": body.question,
            "ideal": body.ideal,
            "ref_files": body.reference_files,
            "meta": None,
            "uid": user_id,
        },
    )
    return rec_id


@router.get("/dataset-records")
async def get_dataset_records(
    dataset_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List records for a dataset."""
    result = await session.execute(
        text(
            "SELECT id, dataset_id, question, ideal, reference_files, metadata, created_at "
            "FROM rag_eval_dataset_records WHERE dataset_id = :ds_id AND user_id = :uid "
            "ORDER BY created_at"
        ),
        {"ds_id": dataset_id, "uid": user_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.delete("/dataset-records/{record_id}")
async def remove_dataset_record(
    record_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a dataset record."""
    await session.execute(
        text("DELETE FROM rag_eval_evaluation_records WHERE dataset_record_id = :id AND user_id = :uid"),
        {"id": record_id, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM rag_eval_dataset_records WHERE id = :id AND user_id = :uid"),
        {"id": record_id, "uid": user_id},
    )
    return {"ok": True}


@router.patch("/dataset-records/{record_id}")
async def update_dataset_record(
    record_id: str,
    body: UpdateDatasetRecordBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a dataset record."""
    sets = []
    params: dict[str, Any] = {"id": record_id, "uid": user_id}
    if body.question is not None:
        sets.append("question = :question")
        params["question"] = body.question
    if body.ideal is not None:
        sets.append("ideal = :ideal")
        params["ideal"] = body.ideal
    if body.reference_files is not None:
        sets.append("reference_files = :ref_files")
        params["ref_files"] = body.reference_files
    if body.metadata is not None:
        sets.append("metadata = :meta")
        params["meta"] = body.metadata
    if not sets:
        return {"ok": True}
    sets.append("updated_at = now()")
    await session.execute(
        text(f"UPDATE rag_eval_dataset_records SET {', '.join(sets)} WHERE id = :id AND user_id = :uid"),
        params,
    )
    return {"ok": True}


@router.post("/dataset-records/import")
async def import_dataset_records(
    body: ImportDatasetRecordsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Batch import dataset records."""
    if not body.dataset_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "dataset_id is required")
    records = body.records
    if records is None and body.pathname:
        try:
            content = await S3Client.from_settings().get_content(body.pathname)
            records = _parse_import_records_content(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Failed to import dataset records from {body.pathname}",
            ) from exc
    count = await _insert_dataset_import_records(
        body.dataset_id,
        records or [],
        user_id=user_id,
        session=session,
    )
    return {"imported": count}


# ── Evaluation CRUD ──────────────────────────────────────────────────


@router.post("/evaluations")
async def create_evaluation(
    body: CreateEvaluationBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a RAG evaluation."""
    eval_id = create_nanoid(32)
    await session.execute(
        text(
            "INSERT INTO rag_eval_evaluations (id, name, description, knowledge_base_id, dataset_id, user_id) "
            "VALUES (:id, :name, :desc, :kb_id, :ds_id, :uid)"
        ),
        {
            "id": eval_id,
            "name": body.name,
            "desc": body.description,
            "kb_id": body.knowledge_base_id,
            "ds_id": body.dataset_id,
            "uid": user_id,
        },
    )
    return eval_id


@router.get("/evaluations")
async def get_evaluation_list(
    knowledge_base_id: str = Query(alias="knowledgeBaseId"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List evaluations for a knowledge base."""
    result = await session.execute(
        text(
            "SELECT id, name, description, knowledge_base_id, dataset_id, status, eval_records_url, created_at "
            "FROM rag_eval_evaluations WHERE knowledge_base_id = :kb_id AND user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"kb_id": knowledge_base_id, "uid": user_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.delete("/evaluations/{evaluation_id}")
async def remove_evaluation(
    evaluation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete an evaluation."""
    await session.execute(
        text("DELETE FROM rag_eval_evaluation_records WHERE evaluation_id = :id AND user_id = :uid"),
        {"id": evaluation_id, "uid": user_id},
    )
    await session.execute(
        text("DELETE FROM rag_eval_evaluations WHERE id = :id AND user_id = :uid"),
        {"id": evaluation_id, "uid": user_id},
    )
    return {"ok": True}


# ── Evaluation Execution ─────────────────────────────────────────────


@router.post("/evaluations/{evaluation_id}/start")
async def start_evaluation_task(
    evaluation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Run a RAG evaluation task."""
    row = await session.execute(
        text(
            "SELECT id, dataset_id, knowledge_base_id, language_model, embedding_model "
            "FROM rag_eval_evaluations WHERE id = :id AND user_id = :uid"
        ),
        {"id": evaluation_id, "uid": user_id},
    )
    eval_row = row.fetchone()
    if not eval_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation not found")

    await session.execute(
        text("UPDATE rag_eval_evaluations SET status = 'processing' WHERE id = :id"),
        {"id": evaluation_id},
    )

    records_result = await session.execute(
        text(
            "SELECT id, question, ideal, reference_files FROM rag_eval_dataset_records "
            "WHERE dataset_id = :dataset_id AND user_id = :uid ORDER BY created_at"
        ),
        {"dataset_id": eval_row.dataset_id, "uid": user_id},
    )
    records = records_result.fetchall()
    await session.execute(
        text("DELETE FROM rag_eval_evaluation_records WHERE evaluation_id = :id AND user_id = :uid"),
        {"id": evaluation_id, "uid": user_id},
    )

    passed = 0
    total_score = 0.0
    output_records: list[dict[str, Any]] = []
    for record in records:
        started = time.monotonic()
        chunks = await lexical_search_chunks(
            session,
            user_id,
            record.question or "",
            limit=5,
            file_ids=record.reference_files,
            kb_ids=[eval_row.knowledge_base_id] if eval_row.knowledge_base_id else None,
        )
        contexts = [chunk.get("text", "") for chunk in chunks]
        answer = "\n\n".join(contexts[:3])
        score, did_pass, reasoning = _score_answer(answer, record.ideal)
        passed += 1 if did_pass else 0
        total_score += score
        eval_record_id = create_nanoid(32)
        error = None if did_pass else {"reason": reasoning, "score": score}
        await session.execute(
            text(
                "INSERT INTO rag_eval_evaluation_records "
                "(id, question, answer, context, ideal, status, error, language_model, embedding_model, "
                "duration, dataset_record_id, evaluation_id, user_id) "
                "VALUES (:id, :question, :answer, :context, :ideal, :status, cast(:error as json), "
                ":language_model, :embedding_model, :duration, :dataset_record_id, :evaluation_id, :uid)"
            ),
            {
                "id": eval_record_id,
                "question": record.question or "",
                "answer": answer,
                "context": contexts,
                "ideal": record.ideal,
                "status": "success" if did_pass else "failed",
                "error": json.dumps(error) if error else None,
                "language_model": eval_row.language_model,
                "embedding_model": eval_row.embedding_model,
                "duration": int((time.monotonic() - started) * 1000),
                "dataset_record_id": record.id,
                "evaluation_id": evaluation_id,
                "uid": user_id,
            },
        )
        output_records.append(
            {
                "id": eval_record_id,
                "datasetRecordId": record.id,
                "score": score,
                "passed": did_pass,
                "reasoning": reasoning,
            }
        )

    total = len(records)
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "avgScore": round(total_score / total, 4) if total else 0,
        "records": output_records,
    }
    await session.execute(
        text(
            "UPDATE rag_eval_evaluations SET status = 'success', eval_records_url = :summary "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": evaluation_id, "uid": user_id, "summary": json.dumps(summary)},
    )
    return {"success": True, "evaluation_id": evaluation_id, "summary": summary}


@router.get("/evaluations/{evaluation_id}/status")
async def check_evaluation_status(
    evaluation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Check the status of a RAG evaluation."""
    result = await session.execute(
        text(
            "SELECT id, status, eval_records_url FROM rag_eval_evaluations "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": evaluation_id, "uid": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation not found")
    return {"id": row[0], "status": row[1], "evalRecordsUrl": row[2], "success": row[1] == "success"}
