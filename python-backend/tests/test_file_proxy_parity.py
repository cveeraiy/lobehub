from __future__ import annotations

from typing import Any

import pytest
from fastapi import status
from fastapi.responses import PlainTextResponse, RedirectResponse

from app.routers import file_proxy


class FakeFile:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeScalarResult:
    def __init__(self, file: FakeFile | None) -> None:
        self.file = file

    def scalar_one_or_none(self) -> FakeFile | None:
        return self.file


class FakeSession:
    def __init__(self, file: FakeFile | None) -> None:
        self.file = file

    async def execute(self, *_args: Any, **_kwargs: Any) -> FakeScalarResult:
        return FakeScalarResult(self.file)


class FakeS3:
    async def create_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://s3.example.test/{key}?expires={expires_in}"


@pytest.mark.asyncio
async def test_file_proxy_redirects_public_urls_without_s3() -> None:
    response = await file_proxy.proxy_file(
        "file-1",
        session=FakeSession(FakeFile("https://cdn.example.test/file.png")),
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://cdn.example.test/file.png"


@pytest.mark.asyncio
async def test_file_proxy_redirects_s3_keys_to_presigned_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_proxy.S3Client, "from_settings", lambda: FakeS3())

    response = await file_proxy.proxy_file(
        "file-1",
        session=FakeSession(FakeFile("files/user-1/image.png")),
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://s3.example.test/files/user-1/image.png?expires=300"


@pytest.mark.asyncio
async def test_file_proxy_returns_404_for_missing_file() -> None:
    response = await file_proxy.proxy_file("missing", session=FakeSession(None))

    assert isinstance(response, PlainTextResponse)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.body == b"File not found"
