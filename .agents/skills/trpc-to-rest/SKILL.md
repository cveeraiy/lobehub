---
name: trpc-to-rest
description: Migrate frontend services from TRPC (lambdaClient) to REST API calls against the Python FastAPI backend. Use when migrating a service file, creating a new REST-backed service, or wiring a store to REST. Triggers on 'trpc to rest', 'rest migration', 'migrate service', 'remove trpc', 'python backend service'.
---

# TRPC → REST Migration Skill

Add parallel REST service implementations alongside existing TRPC services. **No existing frontend code is modified.** A feature-flag resolver lets you switch backends per-domain at runtime.

## Architecture Overview

```
Existing (untouched):          Parallel (new):
  Store                          Store
    ↓                              ↓
  import { svc }                 import { svc }
  from './<domain>'              from './<domain>/resolved'
    ↓                              ↓
  TRPC service                   Resolver (feature flag)
    ↓                              /           \
  lambdaClient                TRPC service   REST service
    ↓                           (existing)     (new .rest.ts)
  TS Backend                       ↓              ↓
                               TS Backend    Python Backend
```

**Key principle:** Existing stores, components, and TRPC services are never changed. REST services are additive. Activation is controlled by env vars.

---

## File Layout Per Domain

Each migrated domain gets this structure:

```
src/services/<domain>/
  index.ts          ← TRPC service (NEVER MODIFIED)
  index.rest.ts     ← REST service (NEW — mirrors same interface)
  resolved.ts       ← Resolver (NEW — picks TRPC or REST via flag)
```

For flat services (e.g., `brief.ts`):

```
src/services/
  brief.ts          ← TRPC service (NEVER MODIFIED)
  brief.rest.ts     ← REST service (NEW)
  brief.resolved.ts ← Resolver (NEW)
```

---

## Feature Flag System

Location: `src/services/_restFlag.ts`

```typescript
import { shouldUseRest } from '@/services/_restFlag';

shouldUseRest('user'); // → true if REST is enabled for 'user' domain
shouldUseRest('brief'); // → true if REST is enabled for 'brief' domain
```

### Env vars

| Variable                              | Effect                                           |
| ------------------------------------- | ------------------------------------------------ |
| `NEXT_PUBLIC_USE_REST_API=1`          | Enable REST for **all** domains                  |
| `NEXT_PUBLIC_REST_DOMAINS=user,brief` | Enable REST only for listed domains              |
| _(unset)_                             | All traffic uses TRPC (default, zero disruption) |

---

## Step-by-Step Migration

### Step 1: Identify the TRPC service

Read the existing service file. Example — `src/services/brief.ts`:

```typescript
// src/services/brief.ts — DO NOT MODIFY
import { lambdaClient } from '@/libs/trpc/client';

class BriefService {
  delete = async (id: string) => {
    return lambdaClient.brief.delete.mutate({ id });
  };
  listUnresolved = async () => {
    return lambdaClient.brief.listUnresolved.query();
  };
  // ...
}
export const briefService = new BriefService();
```

### Step 2: Find the matching Python REST router

Check `python-backend/app/routers/` for the corresponding router.
For briefs: `python-backend/app/routers/briefs.py` → prefix `/api/briefs`

If endpoints are missing, add them to the Python router first.

### Step 3: Create the REST service (`.rest.ts`)

Create `src/services/brief.rest.ts` with the **exact same class name and exported singleton**:

```typescript
import { restClient } from '@/libs/rest';
import type { RestApiResponse } from '@/libs/rest';

class BriefService {
  delete = async (id: string) => {
    return restClient.delete(`/briefs/${id}`);
  };
  listUnresolved = async (): Promise<RestApiResponse> => {
    return restClient.get<RestApiResponse>('/briefs/unresolved');
  };
  // ... same interface as TRPC version
}
export const briefService = new BriefService();
```

### Step 4: Create the resolver (`.resolved.ts`)

Create `src/services/brief.resolved.ts`:

```typescript
import { shouldUseRest } from '@/services/_restFlag';
import { briefService as restService } from './brief.rest';
import { briefService as trpcService } from './brief';

export const briefService = shouldUseRest('brief') ? restService : trpcService;
```

### Step 5: Handle response shape differences

TRPC returns raw data. Python REST may wrap in `{ success, data }`. Match the TRPC return shape inside the `.rest.ts` service so the store never notices:

```typescript
// If TRPC returns raw array but Python wraps in envelope:
listUnresolved = async () => {
  const res = await restClient.get<RestApiResponse<BriefItem[]>>('/briefs/unresolved');
  return { data: res.data ?? [] }; // match TRPC shape
};
```

### Step 6: Handle field casing

- **Preferred:** Python router returns camelCase (Pydantic `alias_generator`).
- **Fallback:** Transform in the `.rest.ts` service layer.
- **Note:** Many Python routers already return camelCase.

### Step 7: Test

1. Enable the domain: `NEXT_PUBLIC_REST_DOMAINS=brief`
2. Start Python backend: `cd python-backend && .venv/bin/uvicorn main:app --reload --port 8000`
3. Start SPA: `PORT=8000 bun run dev:spa`
4. Verify feature works identically
5. Disable the flag → verify TRPC still works

### Step 8: (Optional) Wire into stores

When confident, point stores at the resolver:

```diff
-import { briefService } from '@/services/brief';
+import { briefService } from '@/services/brief.resolved';
```

This is the **only** line that changes in existing code, and only when you're ready. Until then, the `.rest.ts` and `.resolved.ts` files sit dormant.

---

## REST Client API Reference

Location: `src/libs/rest/client.ts`

```typescript
import { restClient } from '@/libs/rest';

// GET with query params
restClient.get<T>('/path', { params: { limit: 50, offset: 0 } });

// POST with JSON body
restClient.post<T>('/path', { body: { title: 'hello' } });

// PUT
restClient.put<T>('/path', { body: { ... } });

// PATCH
restClient.patch<T>('/path', { body: { ... } });

// DELETE
restClient.delete<T>('/path');
```

**Features:**

- Auth headers injected automatically (same as TRPC client)
- 401 handling with login redirect (same as TRPC client)
- Credentials included (cookies sent)
- Base path: `/api` (configurable via `basePath` option)
- Throws `RestClientError` on non-2xx responses

---

## Python Router → Frontend Service Mapping

| Python Router (prefix)         | TS Service File                           | TRPC Namespace              |
| ------------------------------ | ----------------------------------------- | --------------------------- |
| `/api/briefs`                  | `brief.ts`                                | `brief.*`                   |
| `/api/sessions`                | `session/index.ts`                        | `session.*`                 |
| `/api/session-groups`          | `session/index.ts`                        | `sessionGroup.*`            |
| `/api/topics`                  | `topic/index.ts`                          | `topic.*`                   |
| `/api/messages`                | `message/index.ts`                        | `message.*`                 |
| `/api/agents`                  | `agent.ts`                                | `agent.*`                   |
| `/api/agents/{id}/documents`   | `agentDocument.ts`                        | `agentDocument.*`           |
| `/api/threads`                 | `thread/index.ts`                         | `thread.*`                  |
| `/api/knowledge-bases`         | `knowledgeBase.ts`                        | `knowledgeBase.*`           |
| `/api/documents`               | `document/index.ts`                       | `document.*`                |
| `/api/chunks`                  | `rag.ts`                                  | `chunk.*`                   |
| `/api/ai-infra`                | `aiModel/index.ts`, `aiProvider/index.ts` | `aiModel.*`, `aiProvider.*` |
| `/api/files` (+ `/api/upload`) | `file/index.ts`, `upload.ts`              | `file.*`, `upload.*`        |
| `/api/plugins`                 | `plugin/index.ts`                         | `plugin.*`                  |
| `/api/notifications`           | `notification.ts`                         | `notification.*`            |
| `/api/search`                  | `search.ts`                               | `search.*`                  |
| `/api/recent`                  | `recent/index.ts`                         | `recent.*`                  |
| `/api/share`                   | `share.ts`                                | `share.*`                   |
| `/api/export`                  | `export/index.ts`                         | `exporter.*`                |
| `/api/import`                  | `import/index.ts`                         | `importer.*`                |
| `/api/notebook`                | `notebook.ts`                             | `notebook.*`                |
| `/api/user-memory`             | `userMemory/*.ts`                         | `userMemory.*`              |
| `/api/memories`                | `userMemory/*.ts`                         | (overlaps)                  |
| `/api/tasks`                   | `task.ts`                                 | `task.*`                    |
| `/api/agent-cron-jobs`         | `agentCronJob.ts`                         | `agentCronJob.*`            |
| `/api/agent-signal`            | `agentSignal.ts`                          | `agentSignal.*`             |
| `/api/tools`                   | `tool.ts`                                 | (tools router)              |
| `/api/usage`                   | `usage.ts`                                | `usage.*`                   |
| `/api/mcp`                     | `mcp.ts`                                  | (mcp router)                |
| `/api/home`                    | `home/index.ts`                           | `home.*`                    |
| `/api/admin`                   | (admin features)                          | `admin.*`                   |

---

## TRPC Method → REST Method Mapping

| TRPC Pattern                                  | REST Equivalent                                                         |
| --------------------------------------------- | ----------------------------------------------------------------------- |
| `lambdaClient.X.list.query()`                 | `restClient.get('/x')`                                                  |
| `lambdaClient.X.get.query({ id })`            | `restClient.get('/x/{id}')`                                             |
| `lambdaClient.X.create.mutate(body)`          | `restClient.post('/x', { body })`                                       |
| `lambdaClient.X.update.mutate({ id, value })` | `restClient.patch('/x/{id}', { body: value })` or `restClient.put(...)` |
| `lambdaClient.X.delete.mutate({ id })`        | `restClient.delete('/x/{id}')`                                          |
| `lambdaClient.X.search.query({ keywords })`   | `restClient.get('/x', { params: { q: keywords } })`                     |
| `lambdaClient.X.count.query(params)`          | `restClient.get('/x/count', { params })`                                |

---

## Migration Priority Order

Start with simple, low-risk services and work outward:

### Tier 1 — Simple CRUD (start here)

1. `brief.ts` (4 methods, already done as example)
2. `notification.ts` (2-3 methods)
3. `search.ts` (1 method)
4. `share.ts` (2-3 methods)
5. `notebook.ts` (4-5 methods)

### Tier 2 — Medium complexity

6. `topic/index.ts`
7. `session/index.ts`
8. `agent.ts`
9. `agentDocument.ts`
10. `task.ts`

### Tier 3 — Complex / high-traffic

11. `message/index.ts` (many methods, pagination)
12. `file/index.ts` (file upload/download)
13. `aiModel/index.ts` + `aiProvider/index.ts`
14. `home/index.ts` (initial load, critical path)

### Tier 4 — Defer (no Python router yet or special transport)

15. `global.ts` (config — served via `__server_config__`)
16. Streaming endpoints (`aiChat.ts`, `aiAgent.ts`) — use SSE, not JSON
17. `search.ts` — uses `toolsClient`, different TRPC client
18. `discover.ts`, `marketApi.ts` — proxy-based, no Python router
19. `cloudSandbox.ts` — external infra-only
20. `mcp.ts` — uses `toolsClient`, not `lambdaClient`

### Migration Status (completed .rest.ts + .resolved.ts)

| Domain             | Flat/Dir | Done |
| ------------------ | -------- | ---- |
| brief              | flat     | ✅   |
| user               | dir      | ✅   |
| notification       | flat     | ✅   |
| session (+ groups) | dir      | ✅   |
| topic              | dir      | ✅   |
| thread             | dir      | ✅   |
| message            | dir      | ✅   |
| agent              | flat     | ✅   |
| notebook           | flat     | ✅   |
| knowledgeBase      | flat     | ✅   |
| file               | dir      | ✅   |
| upload             | flat     | ✅   |
| home               | dir      | ✅   |
| export             | dir      | ✅   |
| import             | dir      | ✅   |
| plugin             | dir      | ✅   |
| aiModel            | dir      | ✅   |
| aiProvider         | dir      | ✅   |
| chatGroup          | dir      | ✅   |
| document           | dir      | ✅   |
| agentDocument      | flat     | ✅   |
| task               | flat     | ✅   |
| skill              | dir      | ✅   |
| agentEval          | flat     | ✅   |
| generation         | flat     | ✅   |
| generationBatch    | flat     | ✅   |
| generationTopic    | flat     | ✅   |
| recent             | dir      | ✅   |
| followUpAction     | flat     | ✅   |
| rag                | flat     | ✅   |
| ragEval            | flat     | ✅   |
| agentSignal        | flat     | ✅   |
| social             | flat     | ✅   |
| userMemory         | dir      | ✅   |
| usage              | flat     | ✅   |
| agentCronJob       | flat     | ✅   |
| marketApi          | flat     | ✅   |
| tool               | flat     | ✅   |
| agentMarketplace   | flat     | ✅   |
| agentBotProvider   | flat     | ✅   |
| image              | flat     | ✅   |
| video              | flat     | ✅   |
| cloudSandbox       | flat     | ✅   |
| search             | flat     | ✅   |
| mcp                | flat     | ✅   |
| discover           | flat     | ✅   |

---

## Patterns Discovered During Mass Migration

### Pattern 1: Return-value unwrapping

TRPC mutations often return the raw ID as a string. Python REST returns `{ id: "..." }`. The `.rest.ts` service should unwrap:

```typescript
// TRPC returns string directly
createTopic = async (params) => lambdaClient.topic.createTopic.mutate(params);

// REST returns { id: "..." } — unwrap in .rest.ts
createTopic = async (params): Promise<string> => {
  const res = await restClient.post<{ id: string }>('/topics', { body: params });
  return res.id;
};
```

### Pattern 2: Count endpoints

TRPC returns raw number. Python REST returns `{ count: N }`. Unwrap in service:

```typescript
countMessages = async (params?): Promise<number> => {
  const res = await restClient.get<{ count: number }>('/messages/count', { params });
  return res.count;
};
```

### Pattern 3: abortableRequest for debounced mutations

The TRPC message service uses `abortableRequest.execute()` for metadata updates. For REST, the `signal` support is built into `restClient` — just pass `signal` from `RequestOptions`. The `abortableRequest` wrapper is an application-level concern that sits above the service.

### Pattern 4: Private helpers replicated in .rest.ts

If the TRPC service has private helpers like `toDbSessionId()` that transform data before sending, replicate them identically in the `.rest.ts` file. Do not import from the TRPC service.

### Pattern 5: Services that don't use lambdaClient

Some services (e.g., `share.ts`, `onboardingMetrics`, `python.ts`) don't call TRPC at all — they're pure client-side logic. **Skip them** — no `.rest.ts` needed.

### Pattern 6: Import service with uploadService dependency

The import service uses `uploadService` internally for large-file uploads. The `.rest.ts` version keeps this dependency. The upload service itself only has one TRPC call (`createS3PreSignedUrl`) — everything else is XHR.

### Pattern 7: Side-effect replication (cache invalidation)

Services like `agentDocument` call `invalidateDocumentMutation()` after mutations for SWR cache invalidation. The `.rest.ts` must replicate these side effects identically — they're client-side concerns independent of the transport layer.

### Pattern 8: Exported utility functions alongside the service class

Some service files export utility functions (e.g., `mapAgentDocumentsToContext`, `resolveAgentDocumentsContext`, `normalizeAgentDocumentPosition`) alongside the service class. The `.rest.ts` must re-export these identically so consumers of the resolved service get the same module shape.

### Pattern 9: Services using `toolsClient` (not `lambdaClient`) — always deferred

Services like `search.ts` and `mcp.ts` use a different TRPC client (`toolsClient`) that routes to `trpc/tools/` instead of `trpc/lambda/`. These have different auth and batching semantics and should remain deferred.

---

## Common Pitfalls

### 1. Response shape mismatch

TRPC procedures often return raw data. Python REST wraps in `{ success, data, total }`. Always check what the store's `onSuccess` callback expects.

### 2. Field casing

Python uses `snake_case` (e.g., `created_at`), TS expects `camelCase` (`createdAt`). Transform in the service layer if the Python router doesn't alias.

### 3. SuperJSON date handling

TRPC + SuperJSON automatically deserialises ISO strings to `Date` objects. REST returns plain strings. If the store/component does `date.getTime()`, it will break. Either:

- Convert in the service: `new Date(item.createdAt)`
- Or ensure the store treats dates as strings (which most already do)

### 4. Error shape

TRPC errors have `err.data.httpStatus`. REST errors throw `RestClientError` with `.status`. The SWR `onErrorRetry` in `src/libs/swr/index.ts` checks `error?.meta?.shouldRetry` — the `restClient` sets this on 401.

### 5. Batching

TRPC batches multiple queries into one HTTP request. REST doesn't. For initial-load performance, consider combining related queries into a single Python endpoint if latency is a concern.

---

## Checklist for Each Domain Migration

- [ ] Read the TRPC service file (`src/services/<domain>.ts` or `src/services/<domain>/index.ts`)
- [ ] Find the corresponding Python REST router (`python-backend/app/routers/<domain>.py`)
- [ ] Verify all TRPC procedures have matching REST endpoints; add missing ones
- [ ] Create `src/services/<domain>.rest.ts` (or `<domain>/index.rest.ts`) with identical interface
- [ ] Handle response envelope unwrapping inside `.rest.ts` so stores don't notice
- [ ] Handle field casing inside `.rest.ts` if needed
- [ ] Create `src/services/<domain>.resolved.ts` (or `<domain>/resolved.ts`)
- [ ] Test with flag: `NEXT_PUBLIC_REST_DOMAINS=<domain>`
- [ ] Test without flag: verify TRPC path still works
- [ ] Test: 401 triggers login redirect on REST path
- [ ] (Optional) Point store imports at `resolved.ts` when ready

---

## Files Reference

### Infrastructure (shared)

| File                        | Purpose                                                 |
| --------------------------- | ------------------------------------------------------- |
| `src/libs/rest/client.ts`   | REST fetch wrapper with auth, 401 handling, error types |
| `src/libs/rest/types.ts`    | `RestApiResponse<T>`, `RestApiError` types              |
| `src/libs/rest/index.ts`    | Public exports                                          |
| `src/services/_restFlag.ts` | Feature flag: `shouldUseRest(domain)` + env var config  |

### Per-domain (example: brief)

| File                             | Purpose                                 |
| -------------------------------- | --------------------------------------- |
| `src/services/brief.ts`          | TRPC service (**never modified**)       |
| `src/services/brief.rest.ts`     | REST service (parallel, same interface) |
| `src/services/brief.resolved.ts` | Resolver (picks TRPC or REST via flag)  |

### Per-domain (example: user)

| File                              | Purpose                                 |
| --------------------------------- | --------------------------------------- |
| `src/services/user/index.ts`      | TRPC service (**never modified**)       |
| `src/services/user/index.rest.ts` | REST service (parallel, same interface) |
| `src/services/user/resolved.ts`   | Resolver (picks TRPC or REST via flag)  |
