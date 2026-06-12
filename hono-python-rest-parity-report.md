# Hono to Python REST Parity Report

Generated: 2026-05-17

Skill used: `.agents/skills/hono-python-rest-parity`

## Summary

Static inventory found these Hono-backed route surfaces:

- `packages/openapi/src`: 79 operations under `/api/v1/*`, including health.
- `src/hono-server`: 69 application/proxy operations, excluding mounting calls.
- `src/server/workflows-hono`: 12 QStash/internal workflow operations.

Focused Python E2E verification was run against the live Python backend at `http://localhost:8000`:

```bash
cd python-backend
.venv/bin/pytest \
  tests/e2e/test_00_health.py \
  tests/e2e/test_03_agents.py \
  tests/e2e/test_04_topics.py \
  tests/e2e/test_05_messages.py \
  tests/e2e/test_07_files.py \
  tests/e2e/test_09_knowledge.py \
  tests/e2e/test_10_ai_infra.py \
  tests/e2e/test_41_admin.py \
  tests/e2e/test_43_auth.py \
  tests/e2e/test_47_market.py \
  -v --tb=short
```

Result: 69 passed, 1 failed.

Failure:

- `python-backend/tests/e2e/test_41_admin.py::test_get_user_stats` fails with `KeyError: 'user_id'`.
- The Python endpoint `python-backend/app/routers/admin.py:get_user_stats` returns `userId`, while the test expects `user_id`.

## High-Priority Findings

### 1. RBAC OpenAPI Hono endpoints do not have equivalent Python REST endpoints

The Hono OpenAPI package exposes first-class RBAC CRUD endpoints:

| Hono operations                                  | Hono source                                        | Python parity                                                | Test parity        | Status           |
| ------------------------------------------------ | -------------------------------------------------- | ------------------------------------------------------------ | ------------------ | ---------------- |
| `GET/POST /api/v1/roles`                         | `packages/openapi/src/routes/roles.route.ts`       | No `/api/roles` or equivalent role CRUD router found         | No E2E tests found | `missing-python` |
| `GET/PATCH/DELETE /api/v1/roles/:id`             | `packages/openapi/src/routes/roles.route.ts`       | No role detail/update/delete equivalent found                | No E2E tests found | `missing-python` |
| `GET/PATCH/DELETE /api/v1/roles/:id/permissions` | `packages/openapi/src/routes/roles.route.ts`       | No role-permission mapping equivalent found                  | No E2E tests found | `missing-python` |
| `GET/POST /api/v1/permissions`                   | `packages/openapi/src/routes/permissions.route.ts` | No permission CRUD router found                              | No E2E tests found | `missing-python` |
| `GET/PATCH/DELETE /api/v1/permissions/:id`       | `packages/openapi/src/routes/permissions.route.ts` | No permission detail/update/delete equivalent found          | No E2E tests found | `missing-python` |
| `GET/PATCH/DELETE /api/v1/users/:id/roles`       | `packages/openapi/src/routes/users.route.ts`       | Admin/user routers do not expose user-role assignment parity | No E2E tests found | `missing-python` |

Python has `python-backend/app/routers/admin.py` for user management and a Better Auth compatibility surface in `python-backend/app/routers/auth.py`, but neither implements equivalent role and permission CRUD semantics.

### 2. OpenResponses Hono endpoint has no Python REST equivalent

| Hono operation           | Hono source                                      | Python parity                                                    | Test parity                         | Status           |
| ------------------------ | ------------------------------------------------ | ---------------------------------------------------------------- | ----------------------------------- | ---------------- |
| `POST /api/v1/responses` | `packages/openapi/src/routes/responses.route.ts` | No Python `/api/v1/responses` or `/api/responses` endpoint found | No Python E2E/compliance test found | `missing-python` |

The repository has TypeScript compliance support through `packages/openapi`, but the Python backend does not currently expose a matching Response API endpoint.

### 3. File and knowledge-base Python parity exists only partially and tests are weak

| Hono operation group                                          | Hono source                                            | Python endpoint coverage                                                                                                                         | E2E coverage                                                                        | Status           |
| ------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- | ---------------- |
| `GET/POST/PATCH/DELETE /api/v1/files` and `/api/v1/files/:id` | `packages/openapi/src/routes/files.route.ts`           | Python has `python-backend/app/routers/files.py` with create/list/get/update/delete                                                              | `test_07_files.py` only covers list and upload presigned URL                        | `missing-test`   |
| `GET /api/v1/files/:id/url`                                   | same                                                   | No direct equivalent found; closest is presigned/upload-related endpoints                                                                        | No test                                                                             | `missing-python` |
| `POST /api/v1/files/:id/parses`                               | same                                                   | Closest Python operations are `documents.parse-file`, `chunks.create-parse-task`, and file async task helpers, but no same file-scoped operation | No test                                                                             | `missing-python` |
| `POST/GET /api/v1/files/:id/chunks`                           | same                                                   | Closest Python operations are under `/api/chunks/*`                                                                                              | `test_40_chunks.py` covers some chunk operations, not the Hono file-scoped contract | `missing-test`   |
| `POST /api/v1/files/batches`                                  | same                                                   | No direct batch multipart upload parity found                                                                                                    | No test                                                                             | `missing-python` |
| `POST /api/v1/files/queries`                                  | same                                                   | Python has related knowledge-item and file lookup endpoints, but no direct batch file query endpoint found                                       | No test                                                                             | `missing-python` |
| `GET/POST/PATCH/DELETE /api/v1/knowledge-bases`               | `packages/openapi/src/routes/knowledge-bases.route.ts` | Python has `python-backend/app/routers/knowledge.py` for core CRUD                                                                               | `test_09_knowledge.py` covers create/list/delete only                               | `missing-test`   |
| `GET /api/v1/knowledge-bases/:id/files`                       | same                                                   | Python has `GET /api/knowledge-bases/{kb_id}/files`                                                                                              | No E2E test found                                                                   | `missing-test`   |
| `POST/DELETE /api/v1/knowledge-bases/:id/files/batch`         | same                                                   | Python uses different shapes: `POST /api/knowledge-bases/{kb_id}/files`, `POST /api/knowledge-bases/{kb_id}/files/batch-remove`                  | No E2E test found                                                                   | `missing-test`   |
| `POST /api/v1/knowledge-bases/:id/files/move`                 | same                                                   | No direct move-files parity found                                                                                                                | No E2E test found                                                                   | `missing-python` |

### 4. Message translation route parity is incomplete

| Hono operations                                                 | Hono source                                                 | Python parity                                                                                                  | Test parity       | Status           |
| --------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------- | ---------------- |
| `POST/GET/PATCH/DELETE /api/v1/message-translations/:messageId` | `packages/openapi/src/routes/message-translations.route.ts` | Python has `PUT /api/messages/{message_id}/translate`, but no matching create/get/delete translation lifecycle | No E2E test found | `missing-python` |

### 5. Python route ordering likely makes some message/file static endpoints unreachable

In `python-backend/app/routers/messages.py`, dynamic `@router.get("/{message_id}")` appears before static endpoints such as `@router.get("/count")`, `@router.get("/search")`, and `@router.get("/rank-models")`.

In `python-backend/app/routers/files.py`, dynamic `@router.get("/{file_id}")` appears before static endpoints such as `@router.get("/recent")`, `@router.get("/knowledge-items")`, and related static file helper routes.

FastAPI/Starlette route matching is order-sensitive. These routes should be checked and covered with tests before relying on those endpoints for Hono parity.

### 6. Admin test failure blocks full verification

`test_41_admin.py::test_get_user_stats` failed because the endpoint returns camelCase `userId`, while the test expects snake_case `user_id`.

This is a test/API contract mismatch in the existing Python admin API test suite.

## Covered or Mostly Covered Business Operations

| Hono operation group                                                                        | Hono source                                                    | Python equivalent                                                                                      | E2E test file                                                   | Status                                     |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------ |
| Agent CRUD: `GET/POST/PATCH/DELETE /api/v1/agents`                                          | `packages/openapi/src/routes/agents.route.ts`                  | `python-backend/app/routers/agents.py` under `/api/agents`                                             | `python-backend/tests/e2e/test_03_agents.py`                    | `covered`                                  |
| Agent group CRUD: `GET/POST/PATCH/DELETE /api/v1/agent-groups`                              | `packages/openapi/src/routes/agent-groups.route.ts`            | `python-backend/app/routers/agent_groups.py` under `/api/agent-groups`                                 | `python-backend/tests/e2e/test_03_agents.py`                    | `covered`                                  |
| Topic CRUD: `GET/POST/PATCH/DELETE /api/v1/topics`                                          | `packages/openapi/src/routes/topics.route.ts`                  | `python-backend/app/routers/topics.py` under `/api/topics`                                             | `python-backend/tests/e2e/test_04_topics.py`                    | `covered`                                  |
| Message core CRUD: `GET/POST/DELETE /api/v1/messages` and `GET/DELETE /api/v1/messages/:id` | `packages/openapi/src/routes/messages.route.ts`                | `python-backend/app/routers/messages.py` under `/api/messages`                                         | `python-backend/tests/e2e/test_05_messages.py`                  | `covered` for core CRUD                    |
| Provider CRUD: `GET/POST/PATCH/DELETE /api/v1/providers`                                    | `packages/openapi/src/routes/providers.route.ts`               | `python-backend/app/routers/ai_infra.py` under `/api/ai-infra/providers`                               | `python-backend/tests/e2e/test_10_ai_infra.py`                  | `covered` with different path/shape        |
| Model create/list/detail/update: `/api/v1/models`                                           | `packages/openapi/src/routes/models.route.ts`                  | `python-backend/app/routers/ai_infra.py` under `/api/ai-infra/models` and provider-scoped model routes | `python-backend/tests/e2e/test_10_ai_infra.py`                  | `covered` with different path/shape        |
| Auth config: `/api/auth/check-user`, `/api/auth/resolve-username`, `/api/__server_config__` | `src/hono-server/routes/api.ts`                                | `python-backend/app/routers/auth.py`, `python-backend/app/routers/config.py`                           | `python-backend/tests/e2e/test_43_auth.py`, `test_00_health.py` | `covered`                                  |
| Server health/version/config                                                                | `src/hono-server/routes/api.ts`, `packages/openapi/src/app.ts` | `python-backend/main.py`, `python-backend/app/routers/config.py`                                       | `python-backend/tests/e2e/test_00_health.py`                    | `covered`                                  |
| Market agent install/list/uninstall                                                         | `src/hono-server/routes/market/agent.ts`                       | `python-backend/app/routers/market.py` under `/api/market/agents`                                      | `python-backend/tests/e2e/test_47_market.py`                    | `covered` for agent install/list/uninstall |

## Operations With Python Endpoints But Missing or Weak E2E Coverage

| Hono operation                         | Python equivalent                                                  | Existing test gap                                                       | Status           |
| -------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------- | ---------------- |
| `GET /api/v1/messages/count`           | `GET /api/messages/count` exists in `messages.py`                  | No test call found; also likely shadowed by `/{message_id}` route order | `missing-test`   |
| `POST /api/v1/messages/replies`        | No exact endpoint; closest behavior is chat/agent execution        | No test                                                                 | `missing-python` |
| `DELETE /api/v1/messages` batch delete | `DELETE /api/messages` and `POST /api/messages/batch-delete` exist | No E2E coverage in `test_05_messages.py`                                | `missing-test`   |
| `PATCH /api/v1/files/:id`              | `PUT /api/files/{file_id}` exists                                  | No update test in `test_07_files.py`                                    | `missing-test`   |
| `DELETE /api/v1/files/:id`             | `DELETE /api/files/{file_id}` exists                               | No delete test in `test_07_files.py`                                    | `missing-test`   |
| `GET /api/v1/knowledge-bases/:id`      | `GET /api/knowledge-bases/{kb_id}` exists                          | No get-detail test in `test_09_knowledge.py`                            | `missing-test`   |
| `PATCH /api/v1/knowledge-bases/:id`    | `PUT /api/knowledge-bases/{kb_id}` exists                          | No update test in `test_09_knowledge.py`                                | `missing-test`   |
| `GET/PATCH/DELETE /api/v1/users/:id`   | Admin equivalents exist under `/api/admin/users/{user_id}`         | Admin tests cover get/update, but delete is untested                    | `missing-test`   |

## Exempt or Non-REST Surfaces

These Hono routes should not be treated as missing Python REST parity unless the migration goal explicitly includes replacing proxy, webhook, or internal workflow execution paths:

| Hono operation group                                                                                                                                          | Source                                                                    | Reason                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ALL /api/auth/*`                                                                                                                                             | `src/hono-server/auth.ts`                                                 | Better Auth catch-all transport. Python implements specific auth-compatible endpoints, not a full catch-all.                  |
| `ALL /trpc/lambda/*`, `/trpc/async/*`, `/trpc/mobile/*`, `/trpc/tools/*`                                                                                      | `src/hono-server/trpc.ts`                                                 | TRPC transport/proxy surface, not a REST operation.                                                                           |
| `GET *` SPA catch-all                                                                                                                                         | `src/hono-server/spa.ts`                                                  | SPA shell/static rendering.                                                                                                   |
| `ALL /api/v1/*`                                                                                                                                               | `src/hono-server/routes/api.ts`                                           | Delegates to `packages/openapi` Hono app; individual `/api/v1/*` routes are audited separately.                               |
| `/oidc/*` and `/market/oidc/*` catch-alls                                                                                                                     | `src/hono-server/routes/oidc.ts`, `src/hono-server/routes/market/oidc.ts` | OIDC provider protocol transport. Python has limited auth/OIDC compatibility endpoints, not a protocol provider replacement.  |
| `/webapi/chat/:provider`, `/webapi/models/:provider`, `/webapi/tts/*`, `/webapi/stt/openai`, `/webapi/proxy`, `/webapi/trace`, `/webapi/create-image/comfyui` | `src/hono-server/routes/webapi.ts`                                        | Provider proxy/media/trace operations. Python has some chat/image/search routes, but not full `/webapi` proxy parity.         |
| `/api/webhooks/*`                                                                                                                                             | `src/hono-server/routes/webhooks.ts`                                      | Third-party and background callback endpoints. Treat as internal/webhook-specific unless Python is expected to own callbacks. |
| `/api/workflows/agent-eval-run/*`                                                                                                                             | `src/hono-server/routes/workflows.ts`                                     | Workflow callback/execution endpoints. Python has agent evaluation APIs, but not same workflow callback ownership.            |
| `/api/workflows/agent-signal/*`, `/api/workflows/memory-user-memory/*`, `/api/workflows/task/*`                                                               | `src/server/workflows-hono/**`                                            | QStash/internal workflow execution hooks. Python has user-facing APIs for some domains, not these callback paths.             |
| `/f/:id`, `/webapi/user/avatar/:id/:image`                                                                                                                    | `src/hono-server/routes/api.ts`                                           | Redirect/avatar utility endpoints, not normal REST resource CRUD.                                                             |
| `/api/dev/memory-user-memory/benchmark-locomo`                                                                                                                | `src/hono-server/routes/api.ts`                                           | Dev-only benchmark endpoint.                                                                                                  |

## Recommended Fix Plan

1. Decide whether `packages/openapi` `/api/v1/*` is required to be served by Python directly or only semantically mirrored under `/api/*`.
2. Add Python RBAC routers for roles, permissions, and user-role assignment, or document these OpenAPI Hono routes as intentionally out of Python scope.
3. Add Python Response API parity for `POST /api/v1/responses`, or document TypeScript `packages/openapi` as the owner and exclude it from Python migration.
4. Expand Python E2E coverage:
   - `test_07_files.py`: create, get, update, delete, file URL/parse/chunk/batch-query parity.
   - `test_09_knowledge.py`: get, update, file association list/add/remove/move coverage.
   - `test_05_messages.py`: count, batch delete, replies/AI reply behavior, translation behavior if supported.
   - RBAC/admin tests once role/permission endpoints exist.
5. Fix `test_41_admin.py::test_get_user_stats` by aligning the expected key with the Python API contract, or change `admin.py` to return the expected `user_id`.
6. Move static routes before dynamic `/{id}` routes in `messages.py` and `files.py`, then add regression tests for static paths like `/api/messages/count` and `/api/files/recent`.
