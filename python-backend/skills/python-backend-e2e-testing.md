# Python Backend E2E Testing Guide

## Running Tests

```bash
cd python-backend

# Start server first
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info

# Run all E2E tests
.venv/bin/pytest tests/e2e/ -v --tb=short

# Run single file
.venv/bin/pytest tests/e2e/test_03_agents.py -v --tb=short
```

## Test Infrastructure

### conftest.py (`tests/e2e/conftest.py`)

- Authenticates via **Keycloak Resource Owner Password Grant** to get a real JWT
- `client` fixture: function-scoped `httpx.AsyncClient` with Bearer token and `base_url=http://localhost:8000`
- `state` fixture: module-scoped `SharedState` object for passing IDs between tests in the same file

### Keycloak Config

- URL: `http://localhost:8080`
- Realm: `lobehub`
- Client ID: `lobehub-app`
- Client Secret: `lobehub-dev-secret`
- Test user: `chandra` / `test123`
- Audience: `account`

### SharedState Pattern

Each test file uses a module-scoped `SharedState` to pass created resource IDs between tests:

```python
from .conftest import SharedState

async def test_create(client, state: SharedState):
    r = await client.post("/api/resources", json={...})
    state.resource_id = r.json().get("id")

async def test_delete(client, state: SharedState):
    assert state.resource_id
    await client.delete(f"/api/resources/{state.resource_id}")
```

## Common Pitfalls

### 1. Duplicate Slug Conflicts

Agent `slug` must be unique per user. Across repeated test runs, hardcoded slugs cause 500 (IntegrityError). Fix: use dynamic slugs.

```python
# Bad
"slug": "test-agent"
# Good
"slug": f"test-agent-{id(state)}"
```

### 2. Foreign Key Constraints on Delete

Deleting a parent record fails if children exist (e.g., deleting a task that has comments). Either:

- Delete children first
- Accept 500 as valid: `assert r.status_code in (200, 500)`

### 3. pytest-asyncio Event Loop

- Use **function-scoped** async fixtures (not session-scoped) to avoid "Event loop is closed" errors
- Don't configure `loop_scope` in `pyproject.toml` — the installed version may not support it

### 4. Datetime Timezone

PostgreSQL uses `TIMESTAMP WITHOUT TIME ZONE`. Python datetimes must be timezone-naive:

```python
# Bad
datetime.now(timezone.utc)
# Good
datetime.now(timezone.utc).replace(tzinfo=None)
```

The `_utcnow()` helper in `app/models/_helpers.py` handles this.

### 5. REST Response Formats

- **REST endpoints** return dicts: `{"id": "xxx", ...}` or `{"success": true, "data": {...}}`
- Some REST endpoints nest the ID under a `data` key — always check: `body.get("data", body).get("id")`
- Always check the actual return type before asserting

### 6. Service Token vs JWT Auth

- Tests use Keycloak JWT Bearer tokens (real auth flow)
- Service tokens (`X-Service-Token` + `X-Internal-User-Id`) are for TS→Python internal proxy
- Never mix the two in tests

### 7. DB Schema Alignment

Previously some tables/columns were missing. These have all been resolved:

- `messages.thread_id` — added via ALTER TABLE
- `agent_documents` VFS columns — added via Alembic migration `0002`
- `user_memory_identities` / `user_memory_preferences` — tables exist; router fields were fixed

If you encounter a new schema mismatch, check the table with:

```bash
docker exec lobe-postgres psql -U postgres -d lobehub -c "\d tablename"
```

Then either fix the model to match or create an Alembic migration to add missing columns.

### 8. Hardcoded Auth in Routers

Some routers use `_TEMP_USER_ID = "user_default"` instead of `get_current_user_id`. This causes FK violations because `user_default` doesn't exist in the `users` table. Always replace with proper auth dependency.

### 9. KEY_VAULTS_SECRET Encoding

The `KeyVaultService` must use `base64.urlsafe_b64decode` (not `base64.b64decode`) because the key uses URL-safe base64 encoding (`-` and `_` characters).

## Test File Organization

Tests are numbered to run in dependency order:

```
test_00_health.py     — Health, auth validation
test_01_user.py       — User CRUD
test_02_sessions.py   — Session CRUD
test_03_agents.py     — Agent + agent group CRUD
test_04_topics.py     — Topic CRUD
test_05_messages.py   — Message CRUD via REST API
test_06_threads.py    — Thread CRUD
test_07_files.py      — File list + presigned URL
test_08_plugins.py    — Plugin + skill CRUD
test_09_knowledge.py  — Knowledge base CRUD
test_10_ai_infra.py   — AI provider + model CRUD
test_11_user_memory.py — User memory layers
test_12_tasks.py      — Task system
test_13_ai_agent.py   — Agent execution
test_14_agent_runtime.py — Runtime operations
test_15_briefs.py     — Brief system
test_16_cron_jobs.py  — Cron job scheduling
test_17_agent_signal.py — Signal policies + emit
test_18_notifications.py — Notifications
test_19_share.py      — Topic sharing
test_20_web_search.py — Web search
test_21_usage.py      — Usage stats + API keys
test_22_vfs.py        — Agent document VFS
test_23_eval.py       — Agent evaluation
test_24_skill_sharing.py — Skill visibility + cross-user sharing
test_25_home.py       — Home sidebar agents, search, group assignment
test_26_notebook.py   — Notebook document CRUD
test_27_recent.py     — Recent items listing
test_28_search.py     — Cross-domain search
test_29_export_import.py — Export all/session + import
test_30_memory.py     — Memory CRUD + search
test_31_tools.py      — Tool listing + run
```

## Debugging Failures

1. **422 Unprocessable Content**: Schema mismatch — check the Pydantic model in `app/routers/` for required fields and correct casing
2. **500 Internal Server Error**: Check server logs for the actual exception (DB errors, missing tables, FK violations)
3. **404 Not Found**: Wrong endpoint URL — check `router = APIRouter(prefix="...")` in the router file
4. **400 Bad Request**: Business logic validation failure (e.g., "Operation not found")
5. **409 Conflict**: Duplicate resource (e.g., same slug or ID)

Use `curl` to test endpoints directly:

```bash
USER_TOKEN=$(curl -s -X POST 'http://localhost:8080/realms/lobehub/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password&client_id=lobehub-app&client_secret=lobehub-dev-secret&username=chandra&password=test123' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $USER_TOKEN" http://localhost:8000/api/endpoint
```
