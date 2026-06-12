# End-to-End Test Plan: TS Frontend ↔ Python Backend

## Overview

These tests verify that the Python FastAPI backend correctly serves requests
from the TS frontend. Tests exercise two paths:

1. **Direct** — HTTP calls straight to the Python backend (`http://localhost:8000`)
2. **Proxy** — HTTP calls through the TS backend TRPC proxy (`http://localhost:3010`)
   that forwards to Python when `PYTHON_BACKEND_URL` is set

All tests use **service-token auth** (`X-Service-Token` + `X-Internal-User-Id`)
so no real OIDC/JWT setup is needed.

---

## Test Infrastructure

- **Framework**: `pytest` + `httpx.AsyncClient` (Python-native, async)
- **Fixtures**: shared `client` fixture with service-token headers, DB seeding/teardown
- **Config**: `E2E_PYTHON_URL` (default `http://localhost:8000`), `E2E_TS_URL` (optional, `http://localhost:3010`)
- **Marker**: `@pytest.mark.e2e` on all tests; `@pytest.mark.proxy` on proxy-path tests
- **Ordering**: tests within a module run top-to-bottom (create → read → update → delete)

### Prerequisites

```bash
# Terminal 1: Python backend
cd python-backend && uv run uvicorn app.main:app --port 8000

# Terminal 2 (optional, for proxy tests): TS backend
PYTHON_BACKEND_URL=http://localhost:8000 bun run dev

# Terminal 3: Run tests
cd python-backend && .venv/bin/pytest tests/e2e/ -v -m e2e
```

---

## Phase 1 — Auth & Config (foundation)

| #   | Test                                   | Method | Endpoint                                    | Validates                                                      |
| --- | -------------------------------------- | ------ | ------------------------------------------- | -------------------------------------------------------------- |
| 1.1 | Service token auth succeeds            | GET    | `/api/user/state`                           | 200 with valid `X-Service-Token` + `X-Internal-User-Id`        |
| 1.2 | Missing service token → 401            | GET    | `/api/user/state`                           | 401 when no auth headers                                       |
| 1.3 | Invalid service token → 401            | GET    | `/api/user/state`                           | 401 with wrong token                                           |
| 1.4 | Missing user ID with valid token → 400 | GET    | `/api/user/state`                           | 400 when `X-Service-Token` present but no `X-Internal-User-Id` |
| 1.5 | Global config returns valid shape      | GET    | `/trpc/lambda/config.getGlobalConfig`       | 200, has `languageModel`, `defaultAgent` keys                  |
| 1.6 | Default agent config                   | GET    | `/trpc/lambda/config.getDefaultAgentConfig` | 200, has `model`, `provider` keys                              |
| 1.7 | Health check                           | GET    | `/health` or `/api/agent/run`               | 200                                                            |

## Phase 2 — User CRUD

| #    | Test                         | Method | Endpoint                           | Validates                                  |
| ---- | ---------------------------- | ------ | ---------------------------------- | ------------------------------------------ |
| 2.1  | Get user state (auto-create) | GET    | `/api/user/state`                  | 200, user auto-provisioned, has `settings` |
| 2.2  | Update user settings         | PUT    | `/api/user/settings`               | 200, settings persisted                    |
| 2.3  | Update user avatar           | PUT    | `/api/user/avatar`                 | 200                                        |
| 2.4  | Update username              | PUT    | `/api/user/username`               | 200                                        |
| 2.5  | Update fullname              | PUT    | `/api/user/fullname`               | 200                                        |
| 2.6  | Update preference            | PUT    | `/api/user/preference`             | 200                                        |
| 2.7  | Mark user onboarded          | POST   | `/api/user/onboarded`              | 200                                        |
| 2.8  | Reset settings               | DELETE | `/api/user/settings`               | 200, settings back to defaults             |
| 2.9  | TRPC: getUserState           | GET    | `/trpc/lambda/user.getUserState`   | SuperJSON-encoded user state               |
| 2.10 | TRPC: updateSettings         | POST   | `/trpc/lambda/user.updateSettings` | Mutation succeeds                          |

## Phase 3 — Sessions & Session Groups

| #    | Test                      | Method | Endpoint                                   | Validates                            |
| ---- | ------------------------- | ------ | ------------------------------------------ | ------------------------------------ |
| 3.1  | Create session            | POST   | `/api/sessions`                            | 201, returns `id`                    |
| 3.2  | Get sessions (grouped)    | GET    | `/api/sessions`                            | 200, array, contains created session |
| 3.3  | Get single session        | GET    | `/api/sessions/{id}`                       | 200, matches created data            |
| 3.4  | Update session            | PUT    | `/api/sessions/{id}`                       | 200, fields updated                  |
| 3.5  | Create session group      | POST   | `/api/session-groups`                      | 201, returns `id`                    |
| 3.6  | Add session to group      | PUT    | `/api/session-groups/{gid}/sessions/{sid}` | 200                                  |
| 3.7  | Remove session from group | DELETE | `/api/session-groups/{gid}/sessions/{sid}` | 200                                  |
| 3.8  | Delete session group      | DELETE | `/api/session-groups/{gid}`                | 200                                  |
| 3.9  | Delete session            | DELETE | `/api/sessions/{id}`                       | 200                                  |
| 3.10 | TRPC: getGroupedSessions  | GET    | `/trpc/lambda/session.getGroupedSessions`  | Returns grouped structure            |

## Phase 4 — Agents & Agent Groups

| #    | Test                         | Method | Endpoint                                   | Validates                   |
| ---- | ---------------------------- | ------ | ------------------------------------------ | --------------------------- |
| 4.1  | Create agent                 | POST   | `/api/agents`                              | 201, returns `id`           |
| 4.2  | List agents                  | GET    | `/api/agents`                              | 200, contains created agent |
| 4.3  | Get agent by ID              | GET    | `/api/agents/{id}`                         | 200, full agent config      |
| 4.4  | Update agent                 | PUT    | `/api/agents/{id}`                         | 200                         |
| 4.5  | Create agent group           | POST   | `/api/agent-groups`                        | 201                         |
| 4.6  | Add agent to group           | PUT    | `/api/agent-groups/{gid}/agents/{aid}`     | 200                         |
| 4.7  | Remove agent from group      | DELETE | `/api/agent-groups/{gid}/agents/{aid}`     | 200                         |
| 4.8  | Delete agent group           | DELETE | `/api/agent-groups/{gid}`                  | 200                         |
| 4.9  | Link knowledge base to agent | POST   | `/api/agents/{id}/knowledge-bases/{kb_id}` | 201                         |
| 4.10 | Unlink knowledge base        | DELETE | `/api/agents/{id}/knowledge-bases/{kb_id}` | 200                         |
| 4.11 | Delete agent                 | DELETE | `/api/agents/{id}`                         | 200                         |

## Phase 5 — Topics

| #   | Test                       | Method | Endpoint                    | Validates                   |
| --- | -------------------------- | ------ | --------------------------- | --------------------------- |
| 5.1 | Create topic               | POST   | `/api/topics`               | 201, returns `id`           |
| 5.2 | List topics (with session) | GET    | `/api/topics?sessionId=...` | 200, contains created topic |
| 5.3 | Get single topic           | GET    | `/api/topics/{id}`          | 200                         |
| 5.4 | Update topic (rename)      | PUT    | `/api/topics/{id}`          | 200                         |
| 5.5 | Count topics               | TRPC   | `topic.countTopics`         | Number ≥ 1                  |
| 5.6 | Search topics              | TRPC   | `topic.searchTopics`        | Array, keyword match        |
| 5.7 | Delete topic               | DELETE | `/api/topics/{id}`          | 200                         |
| 5.8 | Delete all topics          | DELETE | `/api/topics`               | 200                         |

## Phase 6 — Messages

| #   | Test                     | Method | Endpoint                               | Validates                |
| --- | ------------------------ | ------ | -------------------------------------- | ------------------------ |
| 6.1 | Create user message      | POST   | (TRPC) `message.createMessage`         | Returns message ID       |
| 6.2 | Get messages for topic   | GET    | (TRPC) `message.getMessages`           | Contains created message |
| 6.3 | Update message content   | POST   | (TRPC) `message.updateMessage`         | Content changed          |
| 6.4 | Count messages           | GET    | (TRPC) `message.count`                 | ≥ 1                      |
| 6.5 | Has messages             | GET    | (TRPC) `message.hasMessages`           | true                     |
| 6.6 | Remove single message    | POST   | (TRPC) `message.removeMessage`         | 200                      |
| 6.7 | Remove messages by topic | POST   | (TRPC) `message.removeMessagesByTopic` | 200                      |
| 6.8 | Remove all messages      | POST   | (TRPC) `message.removeAllMessages`     | 200                      |

## Phase 7 — Threads

| #   | Test                | Method | Endpoint                     | Validates               |
| --- | ------------------- | ------ | ---------------------------- | ----------------------- |
| 7.1 | Create thread       | POST   | `/api/threads`               | 201, returns `id`       |
| 7.2 | List threads        | GET    | `/api/threads`               | Contains created thread |
| 7.3 | Get thread by ID    | GET    | `/api/threads/{id}`          | 200                     |
| 7.4 | Update thread       | PUT    | `/api/threads/{id}`          | 200                     |
| 7.5 | Get thread messages | GET    | `/api/threads/{id}/messages` | 200, array              |
| 7.6 | Delete thread       | DELETE | `/api/threads/{id}`          | 200                     |

## Phase 8 — Files & Upload

| #   | Test                     | Method | Endpoint                    | Validates            |
| --- | ------------------------ | ------ | --------------------------- | -------------------- |
| 8.1 | Get presigned upload URL | POST   | `/api/upload/presigned-url` | 200, has `url` field |
| 8.2 | List files               | GET    | (TRPC) `file.getFiles`      | 200, array           |

## Phase 9 — Plugins & Skills

| #    | Test                   | Method | Endpoint                         | Validates  |
| ---- | ---------------------- | ------ | -------------------------------- | ---------- |
| 9.1  | List plugins           | GET    | `/api/plugins`                   | 200, array |
| 9.2  | Install plugin         | POST   | `/api/plugins/install`           | 201        |
| 9.3  | Update plugin settings | PUT    | `/api/plugins/{identifier}`      | 200        |
| 9.4  | Uninstall plugin       | DELETE | `/api/plugins/{identifier}`      | 200        |
| 9.5  | List skills            | GET    | `/api/skills`                    | 200        |
| 9.6  | Create skill           | POST   | `/api/skills`                    | 201        |
| 9.7  | Get skill by ID        | GET    | `/api/skills/{id}`               | 200        |
| 9.8  | Search skills          | GET    | `/api/skills/search/query?q=...` | 200, array |
| 9.9  | Update skill           | PUT    | `/api/skills/{id}`               | 200        |
| 9.10 | Delete skill           | DELETE | `/api/skills/{id}`               | 200        |

## Phase 10 — Knowledge Base & Documents

| #    | Test                    | Method | Endpoint                             | Validates             |
| ---- | ----------------------- | ------ | ------------------------------------ | --------------------- |
| 10.1 | Create knowledge base   | POST   | `/api/knowledge`                     | 201, returns `id`     |
| 10.2 | List knowledge bases    | GET    | `/api/knowledge`                     | Contains created KB   |
| 10.3 | Upload document to KB   | POST   | `/api/documents`                     | 201                   |
| 10.4 | List documents in KB    | GET    | `/api/documents?knowledgeBaseId=...` | Contains uploaded doc |
| 10.5 | Get chunks for document | GET    | `/api/chunks?documentId=...`         | 200, array            |
| 10.6 | Delete document         | DELETE | `/api/documents/{id}`                | 200                   |
| 10.7 | Delete knowledge base   | DELETE | `/api/knowledge/{id}`                | 200                   |

## Phase 11 — AI Infrastructure (Providers & Models)

| #     | Test                    | Method | Endpoint                                   | Validates  |
| ----- | ----------------------- | ------ | ------------------------------------------ | ---------- |
| 11.1  | List AI providers       | GET    | `/api/ai-infra/providers`                  | 200, array |
| 11.2  | Create AI provider      | POST   | `/api/ai-infra/providers`                  | 201        |
| 11.3  | Get provider by ID      | GET    | `/api/ai-infra/providers/{id}`             | 200        |
| 11.4  | Update provider         | PUT    | `/api/ai-infra/providers/{id}`             | 200        |
| 11.5  | Update provider config  | PUT    | `/api/ai-infra/providers/{id}/config`      | 200        |
| 11.6  | Toggle provider enabled | PUT    | `/api/ai-infra/providers/{id}/enabled`     | 200        |
| 11.7  | Reorder providers       | PUT    | `/api/ai-infra/providers/order`            | 200        |
| 11.8  | List provider models    | GET    | `/api/ai-infra/providers/{id}/models`      | 200        |
| 11.9  | Create model            | POST   | `/api/ai-infra/models`                     | 201        |
| 11.10 | Toggle model            | PUT    | `/api/ai-infra/models/toggle`              | 200        |
| 11.11 | Delete model            | DELETE | `/api/ai-infra/models/{id}/provider/{pid}` | 200        |
| 11.12 | Delete provider         | DELETE | `/api/ai-infra/providers/{id}`             | 200        |
| 11.13 | Get runtime config      | GET    | `/api/ai-infra/runtime`                    | 200        |

## Phase 12 — User Memory

| #     | Test                  | Method | Endpoint                            | Validates              |
| ----- | --------------------- | ------ | ----------------------------------- | ---------------------- |
| 12.1  | List memories (empty) | GET    | `/api/user-memory`                  | 200, empty array       |
| 12.2  | Create memory         | POST   | `/api/user-memory`                  | 201                    |
| 12.3  | Get memory by ID      | GET    | `/api/user-memory/{id}`             | 200                    |
| 12.4  | Update memory         | PUT    | `/api/user-memory/{id}`             | 200                    |
| 12.5  | Get memory stats      | GET    | `/api/user-memory/stats`            | 200, has `total` field |
| 12.6  | Create identity       | POST   | `/api/user-memory/identities`       | 201                    |
| 12.7  | List identities       | GET    | `/api/user-memory/identities`       | 200                    |
| 12.8  | Delete identity       | DELETE | `/api/user-memory/identities/{id}`  | 200                    |
| 12.9  | Create preference     | POST   | `/api/user-memory/preferences`      | 201                    |
| 12.10 | List preferences      | GET    | `/api/user-memory/preferences`      | 200                    |
| 12.11 | Delete preference     | DELETE | `/api/user-memory/preferences/{id}` | 200                    |
| 12.12 | Delete memory         | DELETE | `/api/user-memory/{id}`             | 200                    |

## Phase 13 — Tasks

| #     | Test                | Method | Endpoint                   | Validates             |
| ----- | ------------------- | ------ | -------------------------- | --------------------- |
| 13.1  | Create task         | POST   | `/api/tasks`               | 201 or 200            |
| 13.2  | List tasks          | GET    | `/api/tasks`               | Contains created task |
| 13.3  | Get task by ID      | GET    | `/api/tasks/{id}`          | 200                   |
| 13.4  | Update task (patch) | PATCH  | `/api/tasks/{id}`          | 200                   |
| 13.5  | Update task status  | POST   | `/api/tasks/{id}/status`   | 200                   |
| 13.6  | Get task topics     | GET    | `/api/tasks/{id}/topics`   | 200, array            |
| 13.7  | Get task briefs     | GET    | `/api/tasks/{id}/briefs`   | 200, array            |
| 13.8  | Get task comments   | GET    | `/api/tasks/{id}/comments` | 200, array            |
| 13.9  | Add task comment    | POST   | `/api/tasks/{id}/comments` | 201                   |
| 13.10 | Get subtasks        | GET    | `/api/tasks/{id}/subtasks` | 200, array            |
| 13.11 | Delete task         | DELETE | `/api/tasks/{id}`          | 200                   |

## Phase 14 — AI Agent Execution (Proxied)

| #    | Test                         | Method | Endpoint                         | Validates                                |
| ---- | ---------------------------- | ------ | -------------------------------- | ---------------------------------------- |
| 14.1 | Exec agent (basic prompt)    | POST   | `/api/ai-agent/exec`             | 200, has `operationId`, `success`        |
| 14.2 | Exec agent missing agent_id  | POST   | `/api/ai-agent/exec`             | 400 or 422 validation error              |
| 14.3 | Exec group agent             | POST   | `/api/ai-agent/exec-group`       | 200, has `operationId`                   |
| 14.4 | Exec sub-agent task          | POST   | `/api/ai-agent/exec-sub-agent`   | 200                                      |
| 14.5 | Interrupt task               | POST   | `/api/ai-agent/interrupt`        | 200                                      |
| 14.6 | Exec stream (SSE)            | POST   | `/api/ai-agent/exec/stream`      | SSE events: `agent_created`, then stream |
| 14.7 | TS proxy: execAgent via TRPC | POST   | `/trpc/lambda/aiAgent.execAgent` | Same response as 14.1 (via proxy)        |

## Phase 15 — Agent Runtime (Direct Python endpoints)

| #    | Test                   | Method | Endpoint                            | Validates              |
| ---- | ---------------------- | ------ | ----------------------------------- | ---------------------- |
| 15.1 | Create agent operation | POST   | `/api/agent`                        | 200, has `operationId` |
| 15.2 | Get operation status   | GET    | `/api/agent/status/{opId}`          | 200                    |
| 15.3 | List operations        | GET    | `/api/agent/operations`             | 200, array             |
| 15.4 | Interrupt operation    | POST   | `/api/agent/interrupt/{opId}`       | 200                    |
| 15.5 | Delete operation       | DELETE | `/api/agent/{opId}`                 | 200                    |
| 15.6 | Agent SSE stream       | GET    | `/api/agent/stream?operationId=...` | SSE connected event    |
| 15.7 | Agent run health       | GET    | `/api/agent/run`                    | 200                    |

## Phase 16 — Briefs

| #    | Test                  | Method | Endpoint                   | Validates        |
| ---- | --------------------- | ------ | -------------------------- | ---------------- |
| 16.1 | List briefs (empty)   | GET    | `/api/briefs`              | 200, empty array |
| 16.2 | Create brief          | POST   | `/api/briefs`              | 201              |
| 16.3 | Get unresolved briefs | GET    | `/api/briefs/unresolved`   | 200              |
| 16.4 | Resolve brief         | PUT    | `/api/briefs/{id}/resolve` | 200              |
| 16.5 | Dismiss brief         | PUT    | `/api/briefs/{id}/dismiss` | 200              |
| 16.6 | Delete brief          | DELETE | `/api/briefs/{id}`         | 200              |

## Phase 17 — Agent Cron Jobs

| #    | Test               | Method | Endpoint                     | Validates            |
| ---- | ------------------ | ------ | ---------------------------- | -------------------- |
| 17.1 | Create cron job    | POST   | `/api/agent-cron-jobs`       | 201                  |
| 17.2 | List cron jobs     | GET    | `/api/agent-cron-jobs`       | Contains created job |
| 17.3 | Update cron job    | PUT    | `/api/agent-cron-jobs/{id}`  | 200                  |
| 17.4 | Get cron job stats | GET    | `/api/agent-cron-jobs/stats` | 200                  |
| 17.5 | Delete cron job    | DELETE | `/api/agent-cron-jobs/{id}`  | 200                  |

## Phase 18 — Agent Signal

| #    | Test                  | Method | Endpoint                          | Validates        |
| ---- | --------------------- | ------ | --------------------------------- | ---------------- |
| 18.1 | List policies (empty) | GET    | `/api/agent-signal/policies`      | 200, empty array |
| 18.2 | Create policy         | POST   | `/api/agent-signal/policies`      | 201              |
| 18.3 | Emit signal           | POST   | `/api/agent-signal/emit`          | 200              |
| 18.4 | Delete policy         | DELETE | `/api/agent-signal/policies/{id}` | 200              |
| 18.5 | Cleanup stale signals | POST   | `/api/agent-signal/cleanup`       | 200              |

## Phase 19 — Notifications

| #    | Test                   | Method | Endpoint                       | Validates |
| ---- | ---------------------- | ------ | ------------------------------ | --------- |
| 19.1 | List notifications     | GET    | `/api/notifications`           | 200       |
| 19.2 | Mark notification read | PUT    | `/api/notifications/{id}/read` | 200       |
| 19.3 | Mark all read          | PUT    | `/api/notifications/read-all`  | 200       |
| 19.4 | Delete notification    | DELETE | `/api/notifications/{id}`      | 200       |

## Phase 20 — Share & Export/Import

| #    | Test            | Method | Endpoint          | Validates         |
| ---- | --------------- | ------ | ----------------- | ----------------- |
| 20.1 | Create share    | POST   | `/api/share`      | 201, returns `id` |
| 20.2 | Get share by ID | GET    | `/api/share/{id}` | 200               |
| 20.3 | Delete share    | DELETE | `/api/share/{id}` | 200               |

## Phase 21 — Web Search

| #    | Test                       | Method | Endpoint                    | Validates                      |
| ---- | -------------------------- | ------ | --------------------------- | ------------------------------ |
| 21.1 | List search providers      | GET    | `/api/web-search/providers` | 200, non-empty array           |
| 21.2 | Execute search (mock/skip) | POST   | `/api/web-search`           | 200 or skip if no provider key |

## Phase 22 — Usage & API Keys

| #    | Test               | Method | Endpoint              | Validates            |
| ---- | ------------------ | ------ | --------------------- | -------------------- |
| 22.1 | Get usage by month | GET    | `/api/usage/by-month` | 200                  |
| 22.2 | Get usage by day   | GET    | `/api/usage/by-day`   | 200                  |
| 22.3 | Get usage by range | GET    | `/api/usage/by-range` | 200                  |
| 22.4 | Create API key     | POST   | `/api/api-keys`       | 201                  |
| 22.5 | List API keys      | GET    | `/api/api-keys`       | Contains created key |
| 22.6 | Delete API key     | DELETE | `/api/api-keys/{id}`  | 200                  |

## Phase 23 — Agent Document VFS

| #     | Test                     | Method | Endpoint                                | Validates            |
| ----- | ------------------------ | ------ | --------------------------------------- | -------------------- |
| 23.1  | List root (empty)        | POST   | `/api/agent-document-vfs/list`          | 200, empty items     |
| 23.2  | Mkdir                    | POST   | `/api/agent-document-vfs/mkdir`         | 200                  |
| 23.3  | Write file               | POST   | `/api/agent-document-vfs/write`         | 200                  |
| 23.4  | Read file                | POST   | `/api/agent-document-vfs/read`          | 200, content matches |
| 23.5  | Stat file                | POST   | `/api/agent-document-vfs/stat`          | 200, has size/type   |
| 23.6  | Rename file              | POST   | `/api/agent-document-vfs/rename`        | 200                  |
| 23.7  | Copy file                | POST   | `/api/agent-document-vfs/copy`          | 200                  |
| 23.8  | Delete file              | POST   | `/api/agent-document-vfs/delete`        | 200                  |
| 23.9  | Trash list               | POST   | `/api/agent-document-vfs/trash/list`    | 200                  |
| 23.10 | Trash restore            | POST   | `/api/agent-document-vfs/trash/restore` | 200                  |
| 23.11 | Trash delete (permanent) | POST   | `/api/agent-document-vfs/trash/delete`  | 200                  |

## Phase 24 — Agent Eval

| #    | Test                    | Method | Endpoint                           | Validates                  |
| ---- | ----------------------- | ------ | ---------------------------------- | -------------------------- |
| 24.1 | Create benchmark        | POST   | `/api/agent-eval/benchmarks`       | 200                        |
| 24.2 | List benchmarks         | GET    | `/api/agent-eval/benchmarks`       | Contains created benchmark |
| 24.3 | Create dataset          | POST   | `/api/agent-eval/datasets`         | 200                        |
| 24.4 | Create test case        | POST   | `/api/agent-eval/test-cases`       | 200                        |
| 24.5 | Batch create test cases | POST   | `/api/agent-eval/test-cases/batch` | 200                        |
| 24.6 | Create eval run         | POST   | `/api/agent-eval/runs`             | 200                        |
| 24.7 | Get eval run            | GET    | `/api/agent-eval/runs/{id}`        | 200                        |
| 24.8 | Delete benchmark        | DELETE | `/api/agent-eval/benchmarks/{id}`  | 200                        |

---

## Test File Layout

```
python-backend/tests/e2e/
├── conftest.py              # Shared fixtures: client, auth headers, test user
├── test_00_health.py        # Phase 1 — Auth & config
├── test_01_user.py          # Phase 2 — User CRUD
├── test_02_sessions.py      # Phase 3 — Sessions & groups
├── test_03_agents.py        # Phase 4 — Agents & groups
├── test_04_topics.py        # Phase 5 — Topics
├── test_05_messages.py      # Phase 6 — Messages (TRPC)
├── test_06_threads.py       # Phase 7 — Threads
├── test_07_files.py         # Phase 8 — Files & upload
├── test_08_plugins.py       # Phase 9 — Plugins & skills
├── test_09_knowledge.py     # Phase 10 — Knowledge base
├── test_10_ai_infra.py      # Phase 11 — AI providers & models
├── test_11_user_memory.py   # Phase 12 — User memory
├── test_12_tasks.py         # Phase 13 — Tasks
├── test_13_ai_agent.py      # Phase 14 — AI agent execution
├── test_14_agent_runtime.py # Phase 15 — Agent runtime
├── test_15_briefs.py        # Phase 16 — Briefs
├── test_16_cron_jobs.py     # Phase 17 — Cron jobs
├── test_17_agent_signal.py  # Phase 18 — Agent signal
├── test_18_notifications.py # Phase 19 — Notifications
├── test_19_share.py         # Phase 20 — Share
├── test_20_web_search.py    # Phase 21 — Web search
├── test_21_usage.py         # Phase 22 — Usage & API keys
├── test_22_vfs.py           # Phase 23 — Agent document VFS
├── test_23_eval.py          # Phase 24 — Agent eval
└── helpers.py               # TRPC request helpers (SuperJSON encode/decode)
```

## Total: \~170 test cases across 24 phases

### Execution order

Tests are numbered so `pytest` runs them in dependency order:

- Phase 1 (auth) must pass before anything else
- Phase 2 (user) auto-provisions the test user
- Phase 3–7 (sessions, agents, topics, messages, threads) are CRUD building blocks
- Phase 8+ can run independently after the user exists

### Run commands

```bash
# All e2e tests
.venv/bin/pytest tests/e2e/ -v -m e2e

# Single phase
.venv/bin/pytest tests/e2e/test_00_health.py -v

# Only proxy tests (requires TS backend)
.venv/bin/pytest tests/e2e/ -v -m proxy

# With verbose output
.venv/bin/pytest tests/e2e/ -v -s --tb=short
```
