---
name: ethos-repo-migration
description: Use when migrating Ethos Python backend work and REST-only frontend work from lobehub feature branches into the standalone ethos repository. Covers path selection, resolver exclusions, dependency copying, and validation.
---

# Ethos Repo Migration

Use this skill when moving work from `lobehub` into the standalone `ethos` repo.

## Goal

Move only:

- Python backend implementation and tests under `python-backend/**`
- Python backend runtime dependencies, config, and migrations needed by that backend
- REST-only frontend service/client changes needed to call the Python backend
- Focused frontend TypeScript package/tooling setup needed to type-check or test the migrated REST slice

Do not move unrelated product changes, TRPC/REST resolver switchers, branch-wide merges, or speculative cleanup.

## Required Workflow

1. Start with an audit:
   - `git status --short`
   - `git diff --name-only`
   - Include untracked files from `git status`; `git diff --name-only` misses them.
2. Classify every changed file before copying:
   - `backend`: `python-backend/**`
   - `backend dependency`: Python lock/config/migration files used by `python-backend`
   - `rest frontend`: `*.rest.ts`, `*.rest.test.ts`, `src/libs/rest/**`, and direct frontend callers that must import REST services
   - `frontend tooling`: `package.json`, `tsconfig.json`, `vitest.config.*`, test setup files, local package entrypoints, and shims needed by migrated REST files
   - `exclude`: resolver files, unrelated settings, unrelated routes, unrelated UI, broad database migrations not needed by the standalone backend
3. Copy by explicit path list or path-scoped patch. Do not merge or cherry-pick the feature branch wholesale.
4. After copying, inspect the destination diff:
   - No `*.resolved.ts`
   - No `src/services/_restFlag.ts`
   - No imports from resolver files such as `@/services/agent.resolved`
   - No new `src/services/chat/mecha/agentConfigResolver*`
5. Validate with targeted tests before finishing.

## REST-Only Frontend Rules

The standalone repo should use REST directly.

- Import `agentService` from `@/services/agent.rest`
- Import `aiChatService` from `@/services/aiChat.rest`
- Import `notebookService` from `@/services/notebook.rest`
- Import new REST services directly from their `*.rest` module
- Do not add or copy resolver modules whose only job is runtime TRPC/REST switching
- If a copied file imports a resolver, rewrite it to import the REST implementation directly

## Frontend Tooling Rules

The standalone repo may include frontend package/tooling setup, but keep it scoped to the migrated REST slice.

- Add a root `package.json` with scripts for focused checks such as `type-check`, `test`, and `test:rest`.
- Add `tsconfig.json` with aliases matching the migrated code:
  - `@/* -> src/*`
  - `@/types/* -> packages/types/src/*`
  - `@/const/* -> packages/const/src/*`
  - `@/utils/* -> packages/utils/src/*`
  - `@/database/* -> packages/database/src/*`
  - `@lobechat/types`, `@lobechat/const`, `@lobechat/utils`, and `@lobechat/database` to focused local package entrypoints.
- Add `vitest.config.*` and a minimal test setup only when migrated `*.rest.test.ts` files are present.
- For workspace packages that are not migrated, prefer narrow `.d.ts` shims over copying the whole SPA or all workspace packages.
- For local package entrypoints, export only what the migrated REST files need; do not copy broad root barrels that pull in unrelated modules.
- If a REST file imports a non-REST service wrapper such as `@/services/upload` or `@/services/discover`, rewrite it to the direct `.rest` module when available.
- Before committing, run a direct dependency scan from all migrated `*.rest.ts` and `*.rest.test.ts` files and ensure no missing local TypeScript imports remain.

## Python Backend Rules

Copy the backend as a coherent unit:

- Include `python-backend/app/**`, `python-backend/tests/**`, `python-backend/alembic/**`
- Include `python-backend/pyproject.toml`, `python-backend/uv.lock`, `python-backend/alembic.ini`, `.env.example`, and backend README if useful
- Exclude caches and generated local state: `.pytest_cache`, `__pycache__`, `.ruff_cache`, `.venv`

If backend behavior depends on schema changes, prefer Python/Alembic migration files in `python-backend/alembic/**`. Only bring Drizzle migrations from `packages/database/**` when the standalone repo explicitly still runs Drizzle migrations.

## Verification

Recommended checks from the source repo before and after migration:

```bash
cd python-backend
uv run pytest tests/test_provider_runtime.py tests/test_bot_bridge.py tests/test_bot_inbound.py
```

Recommended destination checks:

```bash
rg "\.resolved|_restFlag|agentConfigResolver" .
git status --short
git diff --stat
```

If frontend TypeScript is runnable in the destination repo:

```bash
pnpm install
pnpm type-check
pnpm test:rest
```

If the repo intentionally uses shims for non-migrated workspace packages, note that the checks validate the migrated REST slice and direct local dependencies, not the full SPA.
