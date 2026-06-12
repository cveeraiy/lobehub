---
name: trpc-to-rest
description: Migrate frontend services from TRPC/lambdaClient to canonical REST API calls against the Python FastAPI backend. Use when creating or updating a REST-backed service, removing TRPC frontend code, or wiring stores/features to the Python backend.
---

# TRPC -> REST Migration Skill

The frontend REST migration is now in the canonical phase. Do **not** add `.rest.ts`, `.resolved.ts`, `src/services/_restFlag.ts`, `shouldUseRest`, `NEXT_PUBLIC_USE_REST_API`, or `NEXT_PUBLIC_REST_DOMAINS`.

## Current Pattern

Each frontend service exports its REST implementation directly from the canonical service path:

```ts
// src/services/brief.ts
import { restClient } from '@/libs/rest';

class BriefService {
  listUnresolved = async () => {
    return restClient.get('/briefs/unresolved');
  };
}

export const briefService = new BriefService();
```

Directory services use the same rule:

```text
src/services/user/index.ts
src/services/session/index.ts
src/services/topic/index.ts
```

Stores, routes, features, and packages import only canonical services:

```ts
import { topicService } from '@/services/topic';
import { aiChatService } from '@/services/aiChat';
```

## Migration Steps

1. Find the existing frontend call site or service method.
2. Confirm the Python FastAPI endpoint exists under `python-backend/app/routers`.
3. Implement or update the canonical service method with `restClient`.
4. Normalize response shape, date values, and snake_case/camelCase inside the service layer.
5. Update call sites to import the canonical service path.
6. Delete old frontend TRPC/resolver code for that domain once no call sites remain.
7. Add or update focused Vitest coverage for the service contract.

## REST Client

```ts
import { restClient } from '@/libs/rest';

restClient.get<T>('/path', { params: { limit: 50 } });
restClient.post<T>('/path', { body: { title: 'hello' } });
restClient.put<T>('/path', { body: data });
restClient.patch<T>('/path', { body: data });
restClient.delete<T>('/path');
```

The base path is `/api`; pass resource paths without `/api`.

## Response Compatibility

Keep store/component contracts stable:

- If Python returns `{ id }` but callers expect `string`, unwrap in the service.
- If Python returns `snake_case`, convert to frontend camelCase in the service.
- If callers expect `Date`, convert ISO strings to `Date` in the service.
- If Python uses status aliases, normalize them in the service.

## Validation

Use targeted tests first:

```bash
bunx vitest run --silent='passed-only' src/services/ < domain > .test.ts
bunx tsgo --noEmit --pretty false
```

Stale frontend TRPC scan:

```bash
rg -n "from ['\"](?:@/services|\\.\\.?/).*\\.resolved['\"]|@/libs/trpc/client|lambdaClient\\.|toolsClient\\.|shouldUseRest\\(|_restFlag" src/services src/store src/features src/routes src/layout packages/builtin-tool-* --glob '*.{ts,tsx}'
```

This scan should return no production frontend hits.
