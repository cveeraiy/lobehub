"""Attachment ingestion — upload external files to S3, classify, and parse.

Mirrors TS ``ingestAttachment.ts``.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File, GlobalFile
from app.services.file_service import S3Client, create_file_record

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    file_id: str
    resolved_url: str
    is_image: bool = False
    is_video: bool = False
    file_type: str = "application/octet-stream"


async def fetch_external_file(
    url: Optional[str] = None,
    buffer: Optional[bytes] = None,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> tuple[bytes, str, str]:
    """Fetch file data from URL or use provided buffer.

    Returns (data, filename, content_type).
    """
    if buffer is not None:
        filename = name or "file"
        content_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return buffer, filename, content_type

    if not url:
        raise ValueError("Either url or buffer must be provided")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    data = resp.content
    # Derive filename from URL or Content-Disposition header
    filename = name or url.split("/")[-1].split("?")[0] or "file"
    content_type = (
        mime_type
        or resp.headers.get("content-type", "").split(";")[0].strip()
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    return data, filename, content_type


async def ingest_attachment(
    file_spec: dict[str, Any],
    session: AsyncSession,
    user_id: str,
    s3: Optional[S3Client] = None,
) -> IngestResult:
    """Ingest an external file: download/buffer → S3 → DB record.

    ``file_spec`` keys:
    - ``url`` (str): external URL (fetched if no buffer)
    - ``buffer`` (bytes): pre-downloaded content
    - ``name`` (str): filename
    - ``mimeType`` (str): MIME type
    - ``size`` (int): file size

    Returns :class:`IngestResult` with file_id, resolved_url, and classification.
    """
    data, filename, content_type = await fetch_external_file(
        url=file_spec.get("url"),
        buffer=file_spec.get("buffer"),
        name=file_spec.get("name"),
        mime_type=file_spec.get("mimeType"),
    )

    file_hash = hashlib.sha256(data).hexdigest()
    size = file_spec.get("size") or len(data)

    # Upload to S3
    if s3 is None:
        s3 = S3Client.from_settings()

    s3_key = f"files/{user_id}/{file_hash}/{filename}"
    await s3.upload_bytes(s3_key, data, content_type)

    # Create DB record with dedup
    record = await create_file_record(
        session,
        user_id,
        name=filename,
        url=s3_key,
        file_type=content_type,
        size=size,
        file_hash=file_hash,
    )

    # Classify
    is_image = content_type.startswith("image")
    is_video = content_type.startswith("video")

    return IngestResult(
        file_id=record["file_id"],
        resolved_url=record["url"],
        is_image=is_image,
        is_video=is_video,
        file_type=content_type,
    )
