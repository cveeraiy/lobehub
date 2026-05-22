"""Cloud Sandbox router — execute tools in a self-hosted sandbox environment."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.cloud_sandbox import get_sandbox_service
from app.services.cloud_sandbox.service import guess_mime_type, sandbox_file_hash
from app.services.file_service import S3Client, create_file_record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud-sandbox", tags=["Cloud Sandbox"])


# ── Schemas ──────────────────────────────────────────────────────────

class ExecInSandboxBody(BaseModel):
    tool_name: str = Field(..., alias="toolName")
    params: dict[str, Any] = {}
    topic_id: str = Field(..., alias="topicId")
    user_id: str | None = Field(None, alias="userId")

    model_config = {"populate_by_name": True}


class ExportAndUploadBody(BaseModel):
    path: str
    filename: str | None = None
    topic_id: str = Field(..., alias="topicId")

    model_config = {"populate_by_name": True}


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/exec")
async def exec_in_sandbox(
    body: ExecInSandboxBody,
    user_id: str = Depends(get_current_user_id),
):
    """Execute a tool in the sandbox environment.

    The response mirrors the TS ``tools.market.execInSandbox`` result shape:
    ``{ success, result, sessionExpiredAndRecreated, error? }``.
    """
    effective_user_id = body.user_id or user_id

    try:
        sandbox = get_sandbox_service(effective_user_id, body.topic_id)
        result = await sandbox.call_tool(body.tool_name, body.params)
        return {
            "result": result,
            "sessionExpiredAndRecreated": False,
            "success": True,
        }
    except Exception as exc:
        logger.exception("Sandbox tool execution failed: %s", body.tool_name)
        return {
            "error": {
                "message": str(exc),
                "name": exc.__class__.__name__,
            },
            "result": None,
            "sessionExpiredAndRecreated": False,
            "success": False,
        }


@router.post("/export-and-upload")
async def export_and_upload_file(
    body: ExportAndUploadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Export a file from sandbox and upload to S3.

    Since the sandbox is self-hosted by this backend, we read the sandbox file
    directly, upload it through the Python S3 client, and create the same
    persistent file record that the TS Market flow creates after upload.
    """
    try:
        sandbox = get_sandbox_service(user_id, body.topic_id)
        source_path = sandbox.resolve_path(body.path)
        if not source_path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sandbox file does not exist")

        filename = body.filename or source_path.name
        if "/" in filename or "\\" in filename:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "filename must be a filename")

        data = source_path.read_bytes()
        file_hash = sandbox_file_hash(source_path)
        mime_type = guess_mime_type(source_path)
        today = datetime.now(UTC).date().isoformat()
        key = f"code-interpreter-exports/{today}/{body.topic_id}/{filename}"

        s3 = S3Client.from_settings()
        await s3.upload_bytes(key, data, mime_type)
        metadata = await s3.head(key)

        record = await create_file_record(
            session,
            user_id,
            file_hash=file_hash,
            file_type=metadata.get("content_type") or mime_type,
            name=filename,
            size=int(metadata.get("content_length") or len(data)),
            url=key,
        )

        return {
            "fileId": record["file_id"],
            "filename": filename,
            "mimeType": metadata.get("content_type") or mime_type,
            "size": int(metadata.get("content_length") or len(data)),
            "success": True,
            "url": record["url"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Export and upload failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to export file: {exc}",
        )
