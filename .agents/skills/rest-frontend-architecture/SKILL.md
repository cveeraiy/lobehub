---
name: rest-frontend-architecture
description: How the SPA frontend uses the REST Python backend through canonical service modules. Use when debugging REST calls, checking if a domain uses REST, or tracing frontend data flow to Python FastAPI.
---

# REST Frontend Architecture

The SPA frontend now uses canonical REST services. The old parallel migration layer (`*.rest.ts`, `*.resolved.ts`, `_restFlag`, `shouldUseRest`, and REST env flags) has been removed from app code.

## Architecture

```text
Store / route / feature
  -> canonical service import
  -> restClient
  -> /api/*
  -> Python FastAPI
```

Example:

```ts
import { agentService } from '@/services/agent';

const agent = await agentService.getAgentConfigById(agentId);
```

## Service Rules

- Canonical service files contain the REST implementation directly.
- Do not add resolver files.
- Do not import `@/libs/trpc/client` from frontend app code.
- Normalize backend response differences inside services, not stores.
- Test filenames should be canonical `*.test.ts`, not `*.rest.test.ts`.

## REST Client

`src/libs/rest/client.ts` provides:

```ts
restClient.get<T>('/path', { params });
restClient.post<T>('/path', { body });
restClient.put<T>('/path', { body });
restClient.patch<T>('/path', { body });
restClient.delete<T>('/path');
```

The client sends credentials, handles auth errors, and prefixes requests with `/api`.

## Vite Proxy

SPA development proxies `/api`, `/oidc`, `/webapi`, and legacy `/trpc` routes to the configured backend port. For Python backend development, run the FastAPI server and point the SPA proxy at that port.

## Debugging

- REST calls appear as standard `/api/<resource>` HTTP requests.
- 500 errors should be debugged in the Python backend terminal first.
- If a frontend flow unexpectedly uses TRPC, run the stale scan:

```bash
rg -n "from ['\"](?:@/services|\\.\\.?/).*\\.resolved['\"]|@/libs/trpc/client|lambdaClient\\.|toolsClient\\.|shouldUseRest\\(|_restFlag" src/services src/store src/features src/routes src/layout packages/builtin-tool-* --glob '*.{ts,tsx}'
```
