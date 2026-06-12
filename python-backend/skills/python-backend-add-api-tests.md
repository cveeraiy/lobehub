# Adding E2E Tests for New Python REST API Endpoints

Use this skill whenever a new FastAPI router or endpoint is added to `python-backend/app/routers/`. Every endpoint must have a corresponding E2E test.

---

## Quick Reference

```bash
# Run a single test file
cd python-backend
.venv/bin/pytest tests/e2e/test_XX_name.py -v --tb=short

# Run all E2E tests
.venv/bin/pytest tests/e2e/ -v --tb=short

# Syntax-check a new test file
python3 -m py_compile tests/e2e/test_XX_name.py
```

---

## Step-by-Step Workflow

### 1. Identify the new router and its endpoints

Read the router file to extract every `@router.get/post/put/delete/patch(...)` endpoint:

```bash
grep -n '@router\.\(get\|post\|put\|delete\|patch\)(' app/routers/ < new_router > .py
```

Note the:

- **Prefix**: `APIRouter(prefix="/api/...")` — this is the base path
- **Methods + paths**: Each decorator gives the HTTP method and sub-path
- **Pydantic models**: `CreateXBody`, `UpdateXBody` — these define required/optional fields
- **Auth**: `Depends(get_current_user_id)` means the endpoint requires JWT auth
- **Status codes**: `status_code=status.HTTP_201_CREATED` for create endpoints

### 2. Choose the test file number

Tests are numbered `test_XX_<domain>.py` and run in filename order. Pick the next available number:

```bash
ls tests/e2e/test_*.py | tail -1
```

If the new router depends on resources from other test files (e.g., needs an agent_id), pick a number **after** those dependencies.

### 3. Create the test file

Use this exact template:

```python
"""Phase XX — <Domain>: <brief description of what's tested>."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── XX.1  Create <resource> ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_<resource>(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/<prefix>", json={
        # Required fields from the Pydantic model (snake_case!)
        "field_one": "value",
        "field_two": "value",
    })
    assert r.status_code == 201
    data = r.json()
    state.<resource>_id = data.get("id")
    assert state.<resource>_id


# ── XX.2  List <resources> ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_<resources>(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/<prefix>")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


# ── XX.3  Get single <resource> ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_<resource>(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.<resource>_id
    r = await client.get(f"/api/<prefix>/{state.<resource>_id}")
    assert r.status_code == 200


# ── XX.4  Update <resource> ────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_<resource>(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.<resource>_id
    r = await client.put(f"/api/<prefix>/{state.<resource>_id}", json={
        "field_one": "updated_value",
    })
    assert r.status_code == 200


# ── XX.5  Delete <resource> ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_<resource>(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.<resource>_id
    r = await client.delete(f"/api/<prefix>/{state.<resource>_id}")
    assert r.status_code == 200


# ── XX.6  Cleanup ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    # Delete any prerequisite resources created during setup
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
```

### 4. Adapt the template

**For each endpoint in the router, add a test function.** Rules:

- **One test per endpoint** at minimum (happy path)
- **Test ordering matters** — create before get/update/delete, delete last
- **Setup tests first** if the resource needs prerequisites (session, agent, topic, etc.)
- **Cleanup test last** to remove any created resources

#### Endpoint-to-test mapping:

| Router Endpoint                                       | Test Pattern                                         |
| ----------------------------------------------------- | ---------------------------------------------------- |
| `@router.get("")` (list)                              | `test_list_X` — assert 200, `isinstance(data, list)` |
| `@router.get("/{id}")`                                | `test_get_X` — assert 200, verify ID matches         |
| `@router.post("", status_code=201)`                   | `test_create_X` — assert 201, store ID in state      |
| `@router.put("/{id}")`                                | `test_update_X` — assert 200                         |
| `@router.patch("/{id}")`                              | `test_patch_X` — assert 200                          |
| `@router.delete("/{id}")`                             | `test_delete_X` — assert 200                         |
| `@router.delete("")` (batch)                          | `test_batch_delete_X` — assert 200                   |
| `@router.post("/{id}/sub-resource")`                  | `test_create_sub_resource`                           |
| `@router.get("/search")` or `@router.post("/search")` | `test_search_X`                                      |

### 5. Field naming rules

**All JSON body fields and query parameters MUST use `snake_case`**, matching the Python Pydantic model field names.

```python
# CORRECT — matches Pydantic model
json={"session_id": state.session_id, "title": "Test Topic"}

# WRONG — camelCase is silently ignored by Pydantic
json={"sessionId": state.session_id, "title": "Test Topic"}
```

```python
# CORRECT — snake_case query param matches FastAPI parameter name
r = await client.get(f"/api/topics?session_id={state.session_id}")

# WRONG — FastAPI won't match this param
r = await client.get(f"/api/topics?sessionId={state.session_id}")
```

### 6. Add SharedState fields if needed

If the test stores new resource IDs, add them to `SharedState` in `conftest.py`:

```python
class SharedState:
    # ... existing fields ...
    new_resource_id: str | None = None  # Added for test_XX_<domain>
```

### 7. Verify the test

```bash
# Syntax check
python3 -m py_compile tests/e2e/test_XX_name.py

# Run the test (server must be running)
.venv/bin/pytest tests/e2e/test_XX_name.py -v --tb=short
```

### 8. Update the E2E testing skill

Add the new test file to the test file listing in `skills/python-backend-e2e-testing.md`:

```
test_XX_name.py     — <Description>
```

---

## Fixtures Available

| Fixture           | Scope    | Description                                                        |
| ----------------- | -------- | ------------------------------------------------------------------ |
| `client`          | function | `httpx.AsyncClient` with Keycloak JWT Bearer auth                  |
| `unauthed_client` | function | `httpx.AsyncClient` with no auth headers                           |
| `client_b`        | function | `httpx.AsyncClient` authenticated as User B (for cross-user tests) |
| `base_url`        | session  | `http://localhost:8000`                                            |
| `access_token`    | session  | Raw JWT string for User A                                          |
| `auth_headers`    | session  | `{"Authorization": "Bearer <token>"}`                              |
| `user_id`         | session  | Keycloak `sub` claim for User A                                    |
| `user_id_b`       | session  | Keycloak `sub` claim for User B                                    |
| `state`           | session  | `SharedState` instance for sharing IDs across tests                |

---

## Patterns for Special Endpoint Types

### Endpoints requiring prerequisites

```python
@pytest.mark.asyncio
async def test_setup(client: httpx.AsyncClient, state: SharedState) -> None:
    """Create prerequisite resources."""
    r = await client.post("/api/agents", json={
        "slug": f"test-{id(state)}",
        "title": "Test Agent",
        "system_role": "test",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id")
```

### Endpoints with optional S3/external dependencies

```python
@pytest.mark.asyncio
async def test_presigned_url(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/upload/presigned-url", json={
        "pathname": "test/file.txt",
    })
    # S3 may not be configured in test env
    assert r.status_code in (200, 400, 500)
```

### Endpoints with query params

```python
@pytest.mark.asyncio
async def test_list_with_filters(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.get(
        "/api/resources",
        params={"session_id": state.session_id, "limit": 10},
    )
    assert r.status_code == 200
```

### Batch operations

```python
@pytest.mark.asyncio
async def test_batch_create(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/messages/batch", json=[
        {"role": "user", "content": "msg 1"},
        {"role": "assistant", "content": "msg 2"},
    ])
    assert r.status_code == 201
    assert "ids" in r.json()
```

### Cross-user isolation tests

```python
@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_resource(
    client_b: httpx.AsyncClient, state: SharedState,
) -> None:
    r = await client_b.get(f"/api/resources/{state.resource_id}")
    assert r.status_code in (403, 404)
```

### Unauthed access tests

```python
@pytest.mark.asyncio
async def test_unauthed_returns_401(unauthed_client: httpx.AsyncClient) -> None:
    r = await unauthed_client.get("/api/resources")
    assert r.status_code in (401, 403)
```

---

## Coverage Checklist

For every router in `app/routers/`, verify:

- [ ] Every `@router.get/post/put/delete/patch(...)` has at least one test
- [ ] Create tests store the ID in `SharedState` for subsequent tests
- [ ] Tests use `snake_case` for all JSON body fields and query params
- [ ] Cleanup tests remove resources created during setup
- [ ] `python3 -m py_compile` passes on the test file
- [ ] Test runs green against a running server

### Routers with existing test coverage

| Router                              | Test File                  | Endpoints Covered                                                         |
| ----------------------------------- | -------------------------- | ------------------------------------------------------------------------- |
| `config.py`                         | `test_00_health.py`        | GET /api/version, GET /api/config                                         |
| `user.py`                           | `test_01_user.py`          | state, settings, avatar, username, fullname, preference, onboarded, reset |
| `sessions.py` + `session_groups.py` | `test_02_sessions.py`      | Full CRUD + groups                                                        |
| `agents.py` + `agent_groups.py`     | `test_03_agents.py`        | Full CRUD + groups                                                        |
| `topics.py`                         | `test_04_topics.py`        | Full CRUD                                                                 |
| `messages.py`                       | `test_05_messages.py`      | Create, list, get, update, delete                                         |
| `threads.py`                        | `test_06_threads.py`       | Full CRUD + messages                                                      |
| `files.py` + `upload.py`            | `test_07_files.py`         | List files, presigned URL                                                 |
| `plugins.py` + `skills.py`          | `test_08_plugins.py`       | Full CRUD                                                                 |
| `knowledge.py`                      | `test_09_knowledge.py`     | Create, list, delete                                                      |
| `ai_infra.py`                       | `test_10_ai_infra.py`      | Providers + models CRUD                                                   |
| `user_memory.py`                    | `test_11_user_memory.py`   | All 5 memory layers                                                       |
| `tasks.py`                          | `test_12_tasks.py`         | Full CRUD + comments + status                                             |
| `ai_agent.py`                       | `test_13_ai_agent.py`      | Exec, group, sub-agent, interrupt, stream                                 |
| `agent.py`                          | `test_14_agent_runtime.py` | Runtime operations                                                        |
| `briefs.py`                         | `test_15_briefs.py`        | CRUD + unresolved                                                         |
| `agent_cron_jobs.py`                | `test_16_cron_jobs.py`     | Full CRUD + stats                                                         |
| `agent_signal.py`                   | `test_17_agent_signal.py`  | Policies + emit                                                           |
| `notifications.py`                  | `test_18_notifications.py` | List + mark all read                                                      |
| `share.py`                          | `test_19_share.py`         | Create, get, delete                                                       |
| `web_search.py`                     | `test_20_web_search.py`    | Providers + search                                                        |
| `usage.py` + `api_keys.py`          | `test_21_usage.py`         | by-month, by-day, by-range, API keys                                      |
| `agent_document_vfs.py`             | `test_22_vfs.py`           | Full VFS operations                                                       |
| `agent_eval.py`                     | `test_23_eval.py`          | Benchmarks, datasets, test cases, runs                                    |
| `skills.py` (sharing)               | `test_24_skill_sharing.py` | Visibility, share/unshare, cross-user                                     |
| `home.py`                           | `test_25_home.py`          | Sidebar agents, search, group assignment                                  |
| `notebook.py`                       | `test_26_notebook.py`      | Document CRUD                                                             |
| `recent.py`                         | `test_27_recent.py`        | Recent items listing                                                      |
| `search.py`                         | `test_28_search.py`        | Cross-domain search                                                       |
| `exporter.py` + `importer.py`       | `test_29_export_import.py` | Export all/session + import                                               |
| `memory.py`                         | `test_30_memory.py`        | Memory CRUD + search                                                      |
| `tools.py`                          | `test_31_tools.py`         | Tool listing + run                                                        |

### Routers WITHOUT test coverage (require external deps or special access)

| Router               | Prefix                       | Why untested                                              |
| -------------------- | ---------------------------- | --------------------------------------------------------- |
| `admin.py`           | `/api/admin`                 | Requires admin role — use service token or admin user     |
| `chat.py`            | `/api/chat`                  | Requires LLM API key — stub or skip                       |
| `chunks.py`          | `/api/chunks`                | Depends on RAG pipeline — needs KB + document + embedding |
| `documents.py`       | `/api/documents`             | Depends on file upload + knowledge base                   |
| `agent_documents.py` | `/api/agents/{id}/documents` | Depends on agent + document                               |
| `follow_up.py`       | `/api/follow-up`             | Requires LLM API key                                      |
| `generation.py`      | `/api/generation`            | Requires LLM API key                                      |
| `market.py`          | `/api/market`                | External marketplace                                      |
| `mcp.py`             | `/api/mcp`                   | Requires MCP server connection                            |
| `agent_stream.py`    | `/api/agent-stream`          | SSE streaming — special transport                         |
