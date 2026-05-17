---
name: rest-frontend-architecture
description: How the SPA frontend accommodates the REST Python backend. Covers the parallel service layer, feature flag system, resolved imports, REST client, and Vite proxy. Use when understanding REST mode, debugging REST calls, checking if a domain uses REST, or tracing data flow from store to Python backend. Triggers on 'rest mode', 'rest flag', 'resolved service', 'rest architecture', 'frontend rest', 'shouldUseRest', '_restFlag'.
---

# REST Frontend Architecture

The SPA frontend uses a **parallel service layer** to switch between TRPC (TypeScript backend) and REST (Python backend) without modifying any existing code.

## Architecture Overview

```
Zustand Store (action.ts)
  ↓
import { agentService } from '@/services/agent.resolved'
  ↓
agent.resolved.ts → shouldUseRest('agent')?
  ├── YES → agent.rest.ts → restClient.delete('/api/agents/xxx') → Python FastAPI
  └── NO  → agent.ts → lambdaClient.agent.deleteAgent.mutate() → TRPC → TS Backend
```

**Key principle:** Existing TRPC services are **never modified**. REST services are purely additive. A runtime feature flag controls which backend each domain uses.

## Three Files Per Domain

For each service domain (e.g. `agent`), three files exist:

| File                | Purpose                                     | Modifiable? |
| ------------------- | ------------------------------------------- | ----------- |
| `agent.ts`          | Original TRPC service — uses `lambdaClient` | **NEVER**   |
| `agent.rest.ts`     | REST equivalent — uses `restClient`         | Yes         |
| `agent.resolved.ts` | Runtime resolver — picks TRPC or REST       | Yes         |

### Directory-based services follow the same pattern:

```
src/services/user/
  index.ts          ← TRPC (never modified)
  index.rest.ts     ← REST (new)
  resolved.ts       ← Resolver (new)
```

## Feature Flag System

**File:** `src/services/_restFlag.ts`

```typescript
export const shouldUseRest = (domain: string): boolean => {
  if (GLOBAL_FLAG) return true; // NEXT_PUBLIC_USE_REST_API=1
  return REST_DOMAINS.has(domain); // NEXT_PUBLIC_REST_DOMAINS=user,agent,...
};
```

### Activation

| Env Var                               | Effect                              |
| ------------------------------------- | ----------------------------------- |
| `NEXT_PUBLIC_USE_REST_API=1`          | Enable REST for **all** domains     |
| `NEXT_PUBLIC_REST_DOMAINS=user,agent` | Enable REST only for listed domains |
| _(unset)_                             | All traffic uses TRPC (default)     |

Set these in the root `.env` file. **Requires Vite dev server restart** to take effect.

### Current production config (`.env`):

```
PORT=8000
NEXT_PUBLIC_USE_REST_API=1
```

## Resolver Pattern

Every resolved file follows this exact pattern:

```typescript
// src/services/agent.resolved.ts
import { shouldUseRest } from '@/services/_restFlag';
import { agentService as trpcService } from './agent';
import { agentService as restService } from './agent.rest';

export const agentService = shouldUseRest('agent') ? restService : trpcService;
```

## Store Integration

Stores import from `.resolved` files, not TRPC ones:

```typescript
// src/store/agent/slices/agent/action.ts
import { agentService } from '@/services/agent.resolved';

// This works with BOTH backends — the resolver handles it
const data = await agentService.getAgentConfigById(agentId);
```

## REST Client

**File:** `src/libs/rest/client.ts`

```typescript
import { restClient } from '@/libs/rest';

restClient.get<T>('/path', { params: { limit: 50 } });
restClient.post<T>('/path', { body: { title: 'hello' } });
restClient.put<T>('/path', { body: { ... } });
restClient.patch<T>('/path', { body: { ... } });
restClient.delete<T>('/path');
```

Features:

- Base path: `/api` (all calls go to `/api/<resource>`)
- Auth: credentials included (session cookie sent automatically)
- 401 handling: redirects to login (same as TRPC client)
- Errors: throws `RestClientError` with `.status`

## Vite Proxy

**File:** `vite.config.ts` (line \~314)

```typescript
proxy: {
  '/api': `http://localhost:${process.env.PORT || 3010}`,
  '/oidc': `http://localhost:${process.env.PORT || 3010}`,
  '/trpc': `http://localhost:${process.env.PORT || 3010}`,
  '/webapi': `http://localhost:${process.env.PORT || 3010}`,
},
```

With `PORT=8000` in `.env`, all `/api/*` and `/trpc/*` calls are proxied to the Python backend.

## Response Shape Differences

### TRPC returns raw data, REST may wrap:

```typescript
// TRPC: returns string directly
createTopic = async (params) => lambdaClient.topic.createTopic.mutate(params);

// REST: Python returns { id: "..." } — unwrap in .rest.ts
createTopic = async (params): Promise<string> => {
  const res = await restClient.post<{ id: string }>('/topics', { body: params });
  return res.id; // unwrap to match TRPC shape
};
```

### Count endpoints:

```typescript
// REST .rest.ts must unwrap
countMessages = async (): Promise<number> => {
  const res = await restClient.get<{ count: number }>('/messages/count');
  return res.count;
};
```

## Field Casing

- Python REST returns `snake_case` (`created_at`, `agent_id`)
- TypeScript expects `camelCase` (`createdAt`, `agentId`)
- Transform in the `.rest.ts` service layer, not in stores

## SuperJSON Date Handling

TRPC + SuperJSON auto-converts ISO strings to `Date` objects. REST returns plain strings. If a store does `date.getTime()`, the `.rest.ts` service must convert:

```typescript
return { ...item, createdAt: new Date(item.created_at) };
```

## Migration Status

**All 50 service domains** have `.rest.ts` + `.resolved.ts` files. See the `trpc-to-rest` skill for the full list.

### Remaining direct `lambdaClient` usage (\~28 files):

Some stores, features, and routes still import from TRPC services directly (not `.resolved`). These need to be migrated to use resolved imports for full REST mode support.

## Debugging REST Mode

### Check if REST mode is active:

Open browser console — look for:

```
[_restFlag] USE_REST_API raw = 1 | GLOBAL_FLAG = true
```

If it shows `undefined` / `false`, the `.env` change wasn't picked up. Restart Vite.

### Check which backend a call hits:

- REST calls: `DELETE /api/agents/xxx` (standard HTTP)
- TRPC calls: `GET /trpc/lambda/agent.deleteAgent?...` (batched, SuperJSON)

### 500 errors on REST calls:

1. Check Python backend terminal for the traceback
2. Common causes: FK violations, missing columns, auth issues
3. The `.rest.ts` service may need response shape adjustments

### TRPC fallback still working:

Even with REST mode on, some calls may still go through TRPC if the store imports from the TRPC service directly instead of `.resolved`.
