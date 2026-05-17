"""Phase 23 — Agent Document VFS: mkdir, write, read, stat, rename, copy, delete, trash."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def vfs_agent_id():
    """Placeholder — tests create their own agent if needed."""
    return None


@pytest.mark.asyncio
async def test_setup_agent_for_vfs(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": f"vfs-agent-{id(state)}",
        "title": "VFS Agent",
        "model": "gpt-4o-mini",
        "system_role": "test",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id") or r.json().get("agentId")


@pytest.mark.asyncio
async def test_vfs_list_root(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/list", json={
        "agent_id": state.agent_id,
        "path": "/",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_mkdir(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/mkdir", json={
        "agent_id": state.agent_id,
        "path": "/e2e-test-dir",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_write(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/write", json={
        "agent_id": state.agent_id,
        "path": "/e2e-test-dir/hello.txt",
        "content": "Hello from e2e!",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_read(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/read", json={
        "agent_id": state.agent_id,
        "path": "/e2e-test-dir/hello.txt",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_stat(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/stat", json={
        "agent_id": state.agent_id,
        "path": "/e2e-test-dir/hello.txt",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_rename(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/rename", json={
        "agent_id": state.agent_id,
        "from_path": "/e2e-test-dir/hello.txt",
        "to_path": "/e2e-test-dir/renamed.txt",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_copy(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/copy", json={
        "agent_id": state.agent_id,
        "from_path": "/e2e-test-dir/renamed.txt",
        "to_path": "/e2e-test-dir/copy.txt",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_delete(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/delete", json={
        "agent_id": state.agent_id,
        "path": "/e2e-test-dir",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_vfs_trash_list(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/agent-document-vfs/trash/list", json={
        "agent_id": state.agent_id,
        "path": "/",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.agent_id:
        await client.delete(f"/api/agents/{state.agent_id}")
