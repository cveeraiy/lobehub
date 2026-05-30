from __future__ import annotations

from typing import Any

import pytest
from fastapi import status
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from starlette.datastructures import Headers

from app.routers import file_proxy


class FakeFile:
    def __init__(self, url: str, file_type: str = "image/png", name: str = "image.png") -> None:
        self.url = url
        self.file_type = file_type
        self.name = name


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
    async def get_bytes(self, key: str) -> bytes:
        return b"%PDF-1.4\nbody"


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = Headers(headers or {})


@pytest.mark.asyncio
async def test_file_proxy_redirects_public_urls_without_s3() -> None:
    response = await file_proxy.proxy_file(
        "file-1",
        request=FakeRequest(),
        session=FakeSession(FakeFile("https://cdn.example.test/file.png")),
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "https://cdn.example.test/file.png"


@pytest.mark.asyncio
async def test_file_proxy_serves_s3_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_proxy.S3Client, "from_settings", lambda: FakeS3())

    response = await file_proxy.proxy_file(
        "file-1",
        request=FakeRequest(),
        session=FakeSession(FakeFile("files/user-1/document.pdf", "application/pdf", "document.pdf")),
    )

    assert isinstance(response, Response)
    assert response.status_code == status.HTTP_200_OK
    assert response.body == b"%PDF-1.4\nbody"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="document.pdf"'


@pytest.mark.asyncio
async def test_file_proxy_serves_byte_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_proxy.S3Client, "from_settings", lambda: FakeS3())

    response = await file_proxy.proxy_file(
        "file-1",
        request=FakeRequest({"range": "bytes=0-7"}),
        session=FakeSession(FakeFile("files/user-1/document.pdf", "application/pdf", "document.pdf")),
    )

    assert isinstance(response, Response)
    assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
    assert response.body == b"%PDF-1.4"
    assert response.headers["content-range"] == "bytes 0-7/13"


@pytest.mark.asyncio
async def test_file_proxy_returns_404_for_missing_file() -> None:
    response = await file_proxy.proxy_file("missing", request=FakeRequest(), session=FakeSession(None))

    assert isinstance(response, PlainTextResponse)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.body == b"File not found"
