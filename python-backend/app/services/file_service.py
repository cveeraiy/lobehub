"""File service — S3 storage + global_files dedup.

Mirrors the TS ``FileService`` + ``S3`` module.  Provides:
- S3 upload / download / presigned URLs / delete
- Database record creation with hash-based deduplication via ``global_files``
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from functools import partial
from typing import Any, Optional

import anyio
import boto3
from botocore.config import Config as BotoConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.file import File, GlobalFile

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  S3 Client
# ─────────────────────────────────────────────────────────────────────

class S3Client:
    """Thin wrapper around ``boto3`` S3 client."""

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        endpoint: str,
        bucket: str,
        region: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint,
            region_name=region or "us-east-1",
            config=BotoConfig(s3={"addressing_style": "path"}),
        )

    @classmethod
    def from_settings(cls) -> "S3Client":
        if not settings.s3_access_key_id or not settings.s3_secret_access_key or not settings.s3_endpoint:
            raise RuntimeError("S3 environment variables are not set completely")
        return cls(
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
        )

    # ── Internal sync helpers (called via to_thread) ────────────────
    def _sync_upload_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type,
        )
        return key

    def _sync_get_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def _sync_presigned_url(self, method: str, key: str, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            method, Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in,
        )

    def _sync_delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def _sync_delete_many(self, keys: list[str]) -> None:
        self._client.delete_objects(
            Bucket=self._bucket, Delete={"Objects": [{"Key": k} for k in keys]},
        )

    def _sync_head(self, key: str) -> dict[str, Any]:
        resp = self._client.head_object(Bucket=self._bucket, Key=key)
        return {"content_length": resp.get("ContentLength", 0), "content_type": resp.get("ContentType")}

    # ── Async public API (offloads blocking I/O to a thread) ────────
    async def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return await anyio.to_thread.run_sync(partial(self._sync_upload_bytes, key, data, content_type))

    async def upload_content(self, key: str, content: str) -> str:
        return await self.upload_bytes(key, content.encode(), "text/plain; charset=utf-8")

    async def get_bytes(self, key: str) -> bytes:
        return await anyio.to_thread.run_sync(partial(self._sync_get_bytes, key))

    async def get_content(self, key: str) -> str:
        raw = await self.get_bytes(key)
        return raw.decode()

    async def create_presigned_upload_url(self, key: str, expires_in: int = 3600) -> str:
        return await anyio.to_thread.run_sync(partial(self._sync_presigned_url, "put_object", key, expires_in))

    async def create_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        return await anyio.to_thread.run_sync(partial(self._sync_presigned_url, "get_object", key, expires_in))

    async def delete_file(self, key: str) -> None:
        await anyio.to_thread.run_sync(partial(self._sync_delete, key))

    async def delete_files(self, keys: list[str]) -> None:
        if not keys:
            return
        await anyio.to_thread.run_sync(partial(self._sync_delete_many, keys))

    async def head(self, key: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(partial(self._sync_head, key))


# ─────────────────────────────────────────────────────────────────────
#  File Service (DB records + dedup)
# ─────────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def check_hash(session: AsyncSession, file_hash: str) -> dict[str, Any]:
    """Check if a hash already exists in ``global_files``."""
    stmt = select(GlobalFile).where(GlobalFile.hash_id == file_hash)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return {"is_exist": True, "url": row.url}
    return {"is_exist": False, "url": None}


async def create_file_record(
    session: AsyncSession,
    user_id: str,
    *,
    name: str,
    url: str,
    file_type: str,
    size: int,
    file_hash: str,
    metadata: Optional[dict[str, Any]] = None,
    file_id: Optional[str] = None,
) -> dict[str, str]:
    """Create a ``files`` + optional ``global_files`` record with dedup.

    Returns ``{"file_id": ..., "url": ...}``.
    """
    existing = await check_hash(session, file_hash)

    if not existing["is_exist"]:
        gf = GlobalFile(
            hash_id=file_hash,
            file_type=file_type,
            size=size,
            url=url,
            creator=user_id,
        )
        session.add(gf)

    file_record = File(
        name=name,
        url=url,
        file_type=file_type,
        size=size,
        file_hash=file_hash,
        user_id=user_id,
    )
    if file_id:
        file_record.id = file_id
    if metadata:
        file_record.metadata_ = metadata
    session.add(file_record)
    await session.flush()

    return {"file_id": file_record.id, "url": f"/f/{file_record.id}"}


async def delete_file_record(
    session: AsyncSession,
    user_id: str,
    file_id: str,
    *,
    remove_global: bool = True,
) -> None:
    """Delete a user's file record and optionally the global file."""
    stmt = select(File).where(File.id == file_id, File.user_id == user_id)
    file = (await session.execute(stmt)).scalar_one_or_none()
    if not file:
        return

    if remove_global and file.file_hash:
        gf_stmt = select(GlobalFile).where(GlobalFile.hash_id == file.file_hash)
        gf = (await session.execute(gf_stmt)).scalar_one_or_none()
        if gf:
            await session.delete(gf)

    await session.delete(file)


async def get_file_by_id(
    session: AsyncSession,
    user_id: str,
    file_id: str,
) -> File | None:
    stmt = select(File).where(File.id == file_id, File.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()
