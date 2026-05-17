"""Phase 36 — Video Generation: create batch with generation + async task."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e

_TOPIC_ID: str | None = None


# ── 36.1  Setup: create a generation topic ───────────────────────────

@pytest.mark.asyncio
async def test_setup_generation_topic(client: httpx.AsyncClient) -> None:
    global _TOPIC_ID
    r = await client.post("/api/generation/topics", json={
        "title": "E2E Video Test Topic",
        "type": "text2video",
    })
    if r.status_code in (200, 201):
        data = r.json()
        _TOPIC_ID = data.get("id") or data
    else:
        pytest.skip("Cannot create generation topic")


# ── 36.2  Create text2video generation ───────────────────────────────

@pytest.mark.asyncio
async def test_create_text2video(client: httpx.AsyncClient) -> None:
    if not _TOPIC_ID:
        pytest.skip("No generation topic available")

    r = await client.post("/api/video/create", json={
        "generationTopicId": _TOPIC_ID,
        "model": "gen-3-alpha",
        "provider": "runway",
        "params": {
            "prompt": "A serene ocean wave at sunset",
            "aspectRatio": "16:9",
            "duration": 4,
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "data" in data

    batch = data["data"]["batch"]
    generations = data["data"]["generations"]

    assert batch["model"] == "gen-3-alpha"
    assert batch["provider"] == "runway"
    assert len(generations) == 1
    assert generations[0]["status"] == "pending"
    assert generations[0]["batch_id"] == batch["id"]


# ── 36.3  Create image2video generation ──────────────────────────────

@pytest.mark.asyncio
async def test_create_image2video(client: httpx.AsyncClient) -> None:
    if not _TOPIC_ID:
        pytest.skip("No generation topic available")

    r = await client.post("/api/video/create", json={
        "generationTopicId": _TOPIC_ID,
        "model": "gen-3-alpha",
        "provider": "runway",
        "params": {
            "prompt": "Animate this landscape photo",
            "imageUrl": "https://example.com/landscape.png",
            "duration": 4,
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    generations = data["data"]["generations"]
    assert len(generations) == 1


# ── 36.4  Create video with seed ─────────────────────────────────────

@pytest.mark.asyncio
async def test_create_video_with_seed(client: httpx.AsyncClient) -> None:
    if not _TOPIC_ID:
        pytest.skip("No generation topic available")

    r = await client.post("/api/video/create", json={
        "generationTopicId": _TOPIC_ID,
        "model": "kling-v1",
        "provider": "kuaishou",
        "params": {
            "prompt": "A flower blooming in timelapse",
            "seed": 12345,
            "resolution": "1080p",
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
