---
name: rest-migration-plan
description: Current REST migration and parity checklist for the Python backend and canonical SPA service layer. Use when planning remaining REST work, checking migration status, or choosing validation tests.
---

# REST Migration Plan

The frontend has moved to canonical REST services. Historical resolver/flag migration files are retired and should not be recreated.

## Current Frontend Rules

- Canonical service files under `src/services/**` call `restClient` directly.
- Stores, routes, features, and packages import canonical services only.
- Do not add `.resolved.ts`, `.rest.ts` sidecars, `_restFlag`, `shouldUseRest`, or frontend TRPC client imports.
- Test files should use canonical names such as `agent.test.ts` or `index.test.ts`.
- Response compatibility belongs in services: unwrap payloads, normalize status aliases, convert dates, and map snake_case to camelCase.

## Remaining Work Categories

1. Python endpoint parity
   - Compare Hono/TS router operations against `python-backend/app/routers`.
   - Add missing FastAPI endpoints and Python tests before wiring new frontend calls.

2. Frontend service parity
   - Add or update methods on canonical service modules.
   - Keep public method signatures stable for existing stores/components.
   - Add focused Vitest coverage for risky shape/date/casing normalization.

3. Runtime parity
   - Validate agent runtime, tool execution, RAG/file parsing, eval/task-review, bot, sandbox, and workflow paths through REST/Python.
   - Prefer existing service abstractions over adding transport-specific branches in stores.

4. Dead-code cleanup
   - Remove frontend TRPC clients, resolver files, sidecar REST files, and stale comments once scans prove they are unused.
   - Keep server-side TRPC code only where it still backs legacy server routes or non-frontend compatibility paths.

## Validation Commands

Frontend stale scan:

```bash
rg -n "from ['\"](?:@/services|\\.\\.?/).*\\.resolved['\"]|@/libs/trpc/client|lambdaClient\\.|toolsClient\\.|shouldUseRest\\(|_restFlag" src/services src/store src/features src/routes src/layout packages/builtin-tool-* --glob '*.{ts,tsx}'
find src/services -name '*.rest.test.ts' -o -name '*.rest.ts' -o -name '*resolved*'
```

Typecheck:

```bash
bunx tsgo --noEmit --pretty false
```

Targeted frontend tests:

```bash
bunx vitest run --silent='passed-only' src/services/ < domain > .test.ts
```

Python backend tests:

```bash
cd python-backend
.venv/bin/pytest tests/e2e/test_ -v --tb=short < domain > .py
```

## Completion Criteria

A domain is complete when:

- Python REST endpoints cover the required operations.
- Canonical frontend service methods call REST only.
- No frontend store/route/feature imports `@/libs/trpc/client`.
- No resolver or REST sidecar files remain for the domain.
- Typecheck and targeted tests pass, or any environmental blocker is documented.
