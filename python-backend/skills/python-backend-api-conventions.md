# Python Backend API Conventions

## Field Naming

**All REST API request/response fields use `snake_case`**, matching Python/Pydantic conventions.

Common mistakes (camelCase → snake_case):

| Wrong (camelCase)         | Correct (snake_case)    |
| ------------------------- | ----------------------- |
| `systemRole`              | `system_role`           |
| `topicId`                 | `topic_id`              |
| `providerId`              | `provider_id`           |
| `agentId`                 | `agent_id`              |
| `sessionId`               | `session_id`            |
| `displayName`             | `display_name`          |
| `contentType`             | `content_type`          |
| `sourcePath` / `destPath` | `from_path` / `to_path` |
| `oldPath` / `newPath`     | `from_path` / `to_path` |
| `expectedOutput`          | `expected_output`       |
| `benchmarkId`             | `benchmark_id`          |
| `datasetId`               | `dataset_id`            |

## Required Fields by Endpoint

### Agents (`/api/agents`)

- **Required**: `slug` (unique per user)
- Optional: `title`, `description`, `model`, `system_role`, `tags`, `plugins`

### Tasks (`/api/tasks`)

- **Required**: `identifier`, `instruction`
- Optional: `name`, `description`, `status`, `priority`, `parent_task_id`
- **Status update**: `POST /api/tasks/{id}/status?status=in_progress` (query param, not body)
- **Add comment**: body requires `task_id` and `content`

### Briefs (`/api/briefs`)

- **Required**: `type`, `title`, `summary`
- Optional: `task_id`, `cron_job_id`, `topic_id`, `agent_id`, `priority`, `actions`, `trigger`
- **Response format**: `{"success": true, "data": {"id": ..., ...}}` — ID is nested under `data`

### Agent Cron Jobs (`/api/agent-cron-jobs`)

- **Required**: `agent_id`
- Optional: `name`, `description`, `schedule`, `timezone`, `prompt`

### Knowledge Bases (`/api/knowledge-bases`)

- Endpoint is `/api/knowledge-bases` (NOT `/api/knowledge`)

### Files / Upload (`/api/upload/presigned-url`)

- **Required**: `pathname` (NOT `filename`)

### Skills (`/api/skills`)

- **Required**: `name`, `description` (NOT `displayName`)

### Share (`/api/share`)

- **Required**: `topic_id` (NOT `sessionId` or `type`)

### Agent Signal (`/api/agent-signal`)

- **Policy creation requires**: `id`, `name`
- **Emit requires**: `source`, `type` (NOT `signal_type`)

### Agent Eval (`/api/agent-eval`)

- **Benchmarks require**: `agent_id`, `name`
- **Datasets require**: `benchmark_id`, `name` (in body)
- **Test cases**: `dataset_id` as query param
- **Runs list**: `benchmark_id` as required query param

### Usage (`/api/usage`)

- `/by-range` requires `start` and `end` query params (ISO date `YYYY-MM-DD`)

### VFS (`/api/agent-document-vfs`)

- All endpoints use `agent_id` (snake_case)
- Rename/Copy use `from_path` / `to_path` (NOT `oldPath`/`newPath` or `sourcePath`/`destPath`)

### User Memory (`/api/user-memory`)

- **Base memory**: has `title`, `summary`, `details`, `memory_category`
- **Identities** (`/identities`): fields are `type`, `description`, `role`, `relationship` (NO `title`)
- **Preferences** (`/preferences`): fields are `type`, `conclusion_directives`, `suggestions`, `tags` (NO `title`, NO `description`)

## Auth Patterns

Two auth mechanisms in `app/dependencies.py`:

1. **Keycloak JWT** (primary): Bearer token in `Authorization` header, validated via JWKS
2. **Service token** (internal): `X-Service-Token` + `X-Internal-User-Id` headers for TS→Python proxy

Some routers still use a hardcoded `_TEMP_USER_ID = "user_default"`. Always replace with:

```python
from app.dependencies import get_current_user_id
# Then in endpoint signature:
user_id: str = Depends(get_current_user_id),
```

## Router Prefixes

| Router file             | Prefix                    |
| ----------------------- | ------------------------- |
| `agents.py`             | `/api/agents`             |
| `sessions.py`           | `/api/sessions`           |
| `topics.py`             | `/api/topics`             |
| `messages.py`           | `/api/messages`           |
| `threads.py`            | `/api/threads`            |
| `upload.py`             | `/api/upload`             |
| `skills.py`             | `/api/skills`             |
| `knowledge.py`          | `/api/knowledge-bases`    |
| `ai_infra.py`           | `/api/ai-infra`           |
| `ai_agent.py`           | `/api/ai-agent`           |
| `user_memory.py`        | `/api/user-memory`        |
| `tasks.py`              | `/api/tasks`              |
| `briefs.py`             | `/api/briefs`             |
| `agent_cron_jobs.py`    | `/api/agent-cron-jobs`    |
| `agent_signal.py`       | `/api/agent-signal`       |
| `share.py`              | `/api/share`              |
| `usage.py`              | `/api/usage`              |
| `agent_document_vfs.py` | `/api/agent-document-vfs` |
| `agent_eval.py`         | `/api/agent-eval`         |
