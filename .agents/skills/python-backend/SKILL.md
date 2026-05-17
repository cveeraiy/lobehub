---
name: python-backend
description: Python FastAPI backend development guide. Use when adding/modifying Python routers, services, models, auth, database schemas, or debugging backend 500 errors. Triggers on 'python backend', 'fastapi', 'python router', 'backend endpoint', 'python service', 'alembic migration', 'keycloak auth'.
---

# Python Backend Development Skill

The Python FastAPI backend (`python-backend/`) serves as the REST API layer for the LobeHub SPA. It replaces the TypeScript TRPC backend for all data operations.

## Project Structure

```
python-backend/
├── main.py                    # App entry — FastAPI + router discovery
├── app/
│   ├── config.py              # Pydantic Settings (env vars)
│   ├── db.py                  # SQLAlchemy async engine + session
│   ├── dependencies.py        # Auth: get_current_user_id (Keycloak JWT / service token)
│   ├── feature_flags.py       # Feature flags for the SPA
│   ├── models/                # SQLModel table definitions
│   │   ├── agent.py
│   │   ├── message.py
│   │   ├── user.py
│   │   └── ...
│   ├── routers/               # FastAPI routers (auto-discovered)
│   │   ├── agents.py          # /api/agents
│   │   ├── auth.py            # /api/auth/*, /api/__server_config__
│   │   ├── config.py          # TRPC compat: config.getGlobalConfig
│   │   ├── user.py            # /api/user, TRPC compat: user.getUserState
│   │   ├── sessions.py        # /api/sessions
│   │   ├── messages.py        # /api/messages
│   │   └── ... (48 total)
│   └── services/              # Business logic (packages)
│       ├── chat_service/
│       ├── agent_runtime/
│       ├── llm_service/
│       └── ...
├── alembic/                   # DB migrations (Alembic)
│   └── versions/
└── pyproject.toml             # Dependencies (managed by uv)
```

## Starting the Dev Server

```bash
cd python-backend
uv sync # Install deps into .venv
.venv/bin/uvicorn main:app --reload --port 8000
```

The SPA frontend (`bun run dev:spa`) proxies `/api/*` and `/trpc/*` to `PORT` (set `PORT=8000` in `.env`).

## Router Conventions

### Creating a New Router

1. Create `python-backend/app/routers/<domain>.py`
2. Define `router = APIRouter(prefix="/api/<resource>", tags=["<Resource>"])`
3. Add Pydantic request/response models
4. Use `user_id: str = Depends(get_current_user_id)` on every endpoint
5. Add the module path to `_ROUTER_MODULES` in `main.py`

### Endpoint Design

- **Prefix**: All routers use `/api/<resource>` prefix
- **HTTP methods**: GET reads, POST creates/actions, PUT/PATCH updates, DELETE deletes
- **Status codes**: 200 success, 201 creates, 204 no-content, 404 not found
- **Pagination**: `limit` + `offset` query params, return `total` in response

### Field Casing

**All REST API request/response fields use `snake_case`**, matching Python/Pydantic conventions. The frontend REST service layer transforms to camelCase.

Common mappings:

| Python (snake_case) | TypeScript (camelCase) |
| ------------------- | ---------------------- |
| `system_role`       | `systemRole`           |
| `topic_id`          | `topicId`              |
| `agent_id`          | `agentId`              |
| `session_id`        | `sessionId`            |
| `created_at`        | `createdAt`            |

## Authentication

Two auth mechanisms in `app/dependencies.py:get_current_user_id`:

### 1. Keycloak JWT (Primary)

Users authenticate via Keycloak OIDC → JWT Bearer token.

| Setting       | Dev Value               |
| ------------- | ----------------------- |
| URL           | `http://localhost:8080` |
| Realm         | `lobehub`               |
| Client ID     | `lobehub-app`           |
| Client Secret | `lobehub-dev-secret`    |

```bash
# Get a test token
curl -s -X POST 'http://localhost:8080/realms/lobehub/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password&client_id=lobehub-app&client_secret=lobehub-dev-secret&username=chandra&password=test123'
```

### 2. Session Cookie

The SPA uses signed session cookies (`lobehub_session`) set during the OIDC callback flow (`/api/auth/callback/keycloak`). The session cookie is validated in `dependencies.py` alongside JWT.

### 3. Service Token (Internal TS→Python)

| Header               | Purpose                            |
| -------------------- | ---------------------------------- |
| `X-Service-Token`    | Must match `SERVICE_TOKEN` env var |
| `X-Internal-User-Id` | User ID to act as                  |

### 4. Dev Mock Auth

Set `ENABLE_MOCK_DEV_USER=1` + `MOCK_DEV_USER_ID=<user-id>` to bypass all auth.

**Always use `Depends(get_current_user_id)` — never hardcode user IDs.**

## Database

### Schema Ownership

The PostgreSQL database schema is owned by **TypeScript Drizzle ORM** (`packages/database/`). Python SQLModel models must match the actual DB schema exactly.

### Verifying Schema

```bash
docker exec lobe-postgres psql -U postgres -d lobehub -c "\d tablename"
```

### Datetime Handling

All timestamps use `TIMESTAMP WITHOUT TIME ZONE`. Python datetimes must be timezone-naive:

```python
from datetime import datetime, timezone

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

### Adding New Models

1. Run `\d tablename` to get exact column definitions
2. Match types exactly in SQLModel class
3. If new columns needed: create Alembic migration in `alembic/versions/`
4. Use `sa_column=json_column("field_name")` for JSON columns
5. Run: `.venv/bin/alembic upgrade head`

## TRPC Compatibility Layer

Some SPA calls still use TRPC (`/trpc/lambda/*`). The Python backend has TRPC-compatible routers in:

- `app/routers/config.py` — `config.getGlobalConfig`, `config.getDefaultAgentConfig`
- `app/routers/user.py` — `user.getUserState`
- `app/routers/ai_agent.py` — agent runtime TRPC compat

These return SuperJSON-wrapped responses matching the TRPC v11 wire format.

## Key Configuration (`app/config.py`)

| Env Var                       | Default                 | Purpose                          |
| ----------------------------- | ----------------------- | -------------------------------- |
| `DATABASE_URL`                | (required)              | PostgreSQL connection string     |
| `AUTH_OIDC_ISSUER`            | —                       | Keycloak realm URL               |
| `AUTH_OIDC_CLIENT_ID`         | `lobehub-app`           | OIDC client ID                   |
| `AUTH_OIDC_CLIENT_SECRET`     | —                       | OIDC client secret               |
| `AUTH_DISABLE_EMAIL_PASSWORD` | `True`                  | Hide email/password login        |
| `SESSION_SECRET`              | —                       | Cookie signing secret            |
| `APP_URL`                     | `http://localhost:9876` | Public URL for OIDC redirects    |
| `OPENAI_API_KEY`              | —                       | Default LLM API key              |
| `KEY_VAULTS_SECRET`           | —                       | Encryption key for user API keys |

## Common Issues

### FK Constraint Violations

- Deleting agents fails if they have eval benchmarks, cron jobs, or documents
- Delete cascade: always delete child records first (knowledge bases, files, documents)

### 500 on REST endpoints

1. Check Python server logs (`uvicorn` terminal output)
2. Common causes: missing DB columns, FK violations, timezone-aware datetimes
3. Add `--log-level debug` to uvicorn for verbose SQL logging

### TRPC Transform Errors

If the SPA shows `TRPCClientError: Unable to transform response from server`:

- TRPC error responses must be wrapped in SuperJSON envelope
- HTTP status must match the TRPC error code (e.g., 401 for UNAUTHORIZED)
- See `app/routers/config.py` for the response format
