"""Root file proxy routes for permanent /f/{id} file URLs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.file import File
from app.services.file_service import S3Client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["File Proxy"])


@router.get("/f/{file_id}")
async def proxy_file(file_id: str, session: AsyncSession = Depends(get_db)):
    """Redirect a permanent file proxy URL to a short-lived preview URL."""
    file = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if file is None:
        return PlainTextResponse("File not found", status_code=status.HTTP_404_NOT_FOUND)

    if file.url.startswith("http://") or file.url.startswith("https://"):
        return RedirectResponse(file.url, status_code=status.HTTP_302_FOUND)

    try:
        redirect_url = await S3Client.from_settings().create_presigned_download_url(file.url, expires_in=300)
    except Exception as exc:
        logger.exception("Failed to create file proxy URL for %s", file_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error") from exc

    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
