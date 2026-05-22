"""Phase 6 — Messages: create, list, get, update, delete via REST API."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_setup_session_and_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    """Create prereq session + topic for message tests."""
    r = await client.post("/api/sessions", json={"type": "agent"})
    assert r.status_code == 201
    state.session_id = r.json().get("id")

    r = await client.post("/api/topics", json={"session_id": state.session_id, "title": "Msg Topic"})
    assert r.status_code == 201
    state.topic_id = r.json().get("id")


@pytest.mark.asyncio
async def test_create_message(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id and state.topic_id
    r = await client.post(
        "/api/messages",
        json={
            "content": "Hello from e2e",
            "role": "user",
            "session_id": state.session_id,
            "topic_id": state.topic_id,
        },
    )
    assert r.status_code == 201
    data = r.json()
    state.message_id = data.get("id")
    assert state.message_id


@pytest.mark.asyncio
async def test_get_messages(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id and state.topic_id
    r = await client.get(f"/api/messages?session_id={state.session_id}&topic_id={state.topic_id}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_single_message(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.message_id
    r = await client.get(f"/api/messages/{state.message_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == state.message_id
    assert data["content"] == "Hello from e2e"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_update_message(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.message_id
    r = await client.put(
        f"/api/messages/{state.message_id}",
        json={"content": "Updated from e2e"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_compression_group_persists_summary_and_metadata(
    client: httpx.AsyncClient,
    state: SharedState,
) -> None:
    assert state.session_id and state.topic_id

    message_ids: list[str] = []
    for content in ["Compress me 1", "Compress me 2"]:
        r = await client.post(
            "/api/messages",
            json={
                "content": content,
                "role": "assistant",
                "session_id": state.session_id,
                "topic_id": state.topic_id,
            },
        )
        assert r.status_code == 201
        message_ids.append(r.json()["id"])

    r = await client.post(
        "/api/messages/compression-group",
        json={
            "agent_id": "agent-e2e",
            "message_ids": message_ids,
            "topic_id": state.topic_id,
        },
    )
    assert r.status_code == 200
    group_id = r.json()["message_group_id"]

    r = await client.post(
        "/api/messages/compression-group/finalize",
        json={
            "agent_id": "agent-e2e",
            "content": "Compressed summary",
            "message_group_id": group_id,
            "topic_id": state.topic_id,
        },
    )
    assert r.status_code == 200

    r = await client.put(
        f"/api/messages/{group_id}/group-metadata",
        json={"context": {"topic_id": state.topic_id}, "expanded": False},
    )
    assert r.status_code == 200
    groups = [item for item in r.json()["messages"] if item["id"] == group_id]
    assert groups
    assert groups[0]["content"] == "Compressed summary"
    assert groups[0]["metadata"] == {"expanded": False}


@pytest.mark.asyncio
async def test_remove_message(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.message_id:
        pytest.skip("No message to delete")
    r = await client.delete(f"/api/messages/{state.message_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.topic_id:
        await client.delete(f"/api/topics/{state.topic_id}")
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
