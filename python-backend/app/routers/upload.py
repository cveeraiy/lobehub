"""Upload router — S3 pre-signed URL generation for client-side direct upload."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_current_user_id
from app.services.file_service import S3Client

router = APIRouter(prefix="/api/upload", tags=["Upload"])


class PreSignedUrlBody(BaseModel):
    pathname: str


@router.post("/presigned-url")
async def create_presigned_url(
    body: PreSignedUrlBody,
    user_id: str = Depends(get_current_user_id),
):
    """Generate a pre-signed S3 URL for direct client upload.

    The client can PUT a file directly to the returned URL without
    going through the server.
    """
    s3 = S3Client.from_settings()
    url = await s3.create_presigned_upload_url(body.pathname)
    return {"url": url, "pathname": body.pathname}
