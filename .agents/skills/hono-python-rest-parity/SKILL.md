---
name: hono-python-rest-parity
description: Validate that Hono backend operations have equivalent Python FastAPI REST endpoints and implemented API/E2E tests. Use when auditing Hono-to-Python REST parity, checking migration coverage, finding missing Python routers, or verifying Python backend API tests for Hono operations.
---

# Hono to Python REST Parity

Use this skill to audit Hono backend endpoints and confirm each operation has:

1. an equivalent Python FastAPI REST endpoint under `python-backend/app/routers/`
2. API/E2E coverage under `python-backend/tests/e2e/`
3. passing targeted tests, or a clearly documented gap

## Scope

Audit server-side Hono operations from:

- `src/hono-server/**/*.ts`
- `src/server/workflows-hono/**/*.ts`
- `packages/openapi/src/routes/**/*.ts`
- `packages/openapi/src/app.ts`

Treat each `app.get/post/put/patch/delete(...)` and each mounted `route(...)` as an operation to map. Include the mounted base path when determining the full path.

Common non-business endpoints may be marked "exempt" only with a reason:

- health checks
- SPA shell/static rendering
- TRPC transport/proxy routes that are not REST API operations
- third-party webhook callbacks without a Python REST equivalent requirement
- QStash/internal workflow hooks when the Python backend intentionally does not own that execution path

Do not silently ignore exemptions. List them in the final report.

## Fast Inventory

From the repo root:

```bash
rg -n "new Hono|\\.route\\(|\\.(get|post|put|patch|delete)\\(" src/hono-server src/server/workflows-hono packages/openapi/src --glob '*.{ts,tsx,mts}'
```

Extract Python endpoints:

```bash
rg -n "APIRouter\\(|@router\\.(get|post|put|patch|delete)\\(" python-backend/app/routers python-backend/main.py --glob '*.py'
```

Extract Python API tests:

```bash
rg -n "client\\.(get|post|put|patch|delete)\\(" python-backend/tests/e2e --glob '*.py'
```

When the route tree is unclear, read the mounting file first:

- Hono: `src/hono-server/index.ts`, `packages/openapi/src/app.ts`, `src/server/workflows-hono/index.ts`
- Python: `python-backend/main.py`

## Mapping Rules

Create a parity table with one row per Hono operation:

| Hono method/path | Hono file | Expected Python method/path | Python router | Test file | Status | Notes |
| ---------------- | --------- | --------------------------- | ------------- | --------- | ------ | ----- |

Status values:

- `covered`: Python endpoint exists and a test calls the same behavior
- `missing-python`: no Python REST equivalent found
- `missing-test`: Python endpoint exists but no API/E2E test covers it
- `untested`: test exists but could not be run in this session
- `failing`: targeted test was run and failed
- `exempt`: intentionally no Python equivalent; include the reason

Path matching is semantic, not just string equality:

- Hono `/api/v1/files/:id` can map to FastAPI `/api/files/{file_id}` if the operation and resource semantics match.
- Hono camelCase request fields may map to Python snake_case only if the frontend/service adapter or Python model explicitly supports the mapping.
- Authentication must be equivalent. Hono operations requiring auth should map to Python endpoints using `Depends(get_current_user_id)` or a documented internal auth dependency.
- Status codes and response shapes should be compatible with existing frontend clients or OpenAPI clients.

## Test Coverage Rules

Every non-exempt Python equivalent must have a test in `python-backend/tests/e2e/`.

Minimum acceptable coverage:

- one happy-path API test per endpoint
- create/list/get/update/delete flows preserve dependency order
- tests use real `httpx.AsyncClient` fixtures from `python-backend/tests/e2e/conftest.py`
- tests use JWT/client fixtures unless the endpoint is intentionally internal
- test request fields match Python Pydantic models, normally `snake_case`

Prefer existing domain files such as:

- `test_07_files.py` for files/upload
- `test_09_knowledge.py` for knowledge base operations
- `test_43_auth.py` for auth/session behavior
- `test_47_market.py` for market routes

If adding tests, follow `python-backend/skills/python-backend-add-api-tests.md` and update `python-backend/skills/python-backend-e2e-testing.md` if a new test file is introduced.

## Verification

Run targeted tests for the affected domains:

```bash
cd python-backend
.venv/bin/pytest tests/e2e/test_XX_domain.py -v --tb=short
```

For broad audits, run only the domain files needed to support the parity claim. Do not run the full test suite unless the user explicitly asks.

If the Python server or dependencies are not running, still complete the static audit and mark runnable tests as `untested` with the blocker.

## Report Format

Lead with findings, not process:

1. missing Python endpoints
2. missing or weak tests
3. failing tests
4. exempt operations
5. covered operations summary

For each gap, include exact file references and the concrete endpoint or test that should be added.

If all checked operations are covered, say so directly and list the tests that were run.
