"""Root file proxy routes for permanent /f/{id} file URLs."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.file import File
from app.services.file_service import S3Client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["File Proxy"])


@router.get("/f/{file_id}")
async def proxy_file(file_id: str, request: Request, session: AsyncSession = Depends(get_db)):
    """Serve a permanent file proxy URL."""
    file = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if file is None:
        return PlainTextResponse("File not found", status_code=status.HTTP_404_NOT_FOUND)

    if file.url.startswith("http://") or file.url.startswith("https://"):
        return RedirectResponse(file.url, status_code=status.HTTP_302_FOUND)

    try:
        data = await S3Client.from_settings().get_bytes(file.url)
    except Exception as exc:
        logger.exception("Failed to read file proxy bytes for %s", file_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error") from exc

    content_type = file.file_type or "application/octet-stream"
    filename = (file.name or file_id).replace('"', "")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{filename}"',
    }

    range_header = request.headers.get("range")
    if range_header:
        match = re.match(r"bytes=(\d*)-(\d*)$", range_header)
        if match:
            start_text, end_text = match.groups()
            start = int(start_text) if start_text else 0
            end = int(end_text) if end_text else len(data) - 1
            end = min(end, len(data) - 1)

            if 0 <= start <= end:
                chunk = data[start : end + 1]
                headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
                headers["Content-Length"] = str(len(chunk))
                return Response(
                    chunk,
                    headers=headers,
                    media_type=content_type,
                    status_code=status.HTTP_206_PARTIAL_CONTENT,
                )

        return Response(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)

    headers["Content-Length"] = str(len(data))
    return Response(data, headers=headers, media_type=content_type)
