# Ethos Python Backend

FastAPI backend for Ethos — chat, agents, knowledge bases, memory, tools, and admin.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- (Optional) Keycloak for OIDC auth
- (Optional) S3-compatible storage (MinIO / AWS S3)

### 1. Install dependencies

```bash
# Using uv (recommended)
uv sync

# Or pip
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

Key environment variables:

| Variable               | Required | Description                                     |
| ---------------------- | -------- | ----------------------------------------------- |
| `DATABASE_URL`         | Yes      | PostgreSQL async connection string              |
| `AUTH_OIDC_ISSUER`     | No       | Keycloak realm URL (disables auth if unset)     |
| `AUTH_OIDC_CLIENT_ID`  | No       | OIDC client ID (default: `lobehub-backend`)     |
| `KEY_VAULTS_SECRET`    | No       | Fernet key for encrypting provider API keys     |
| `S3_ACCESS_KEY_ID`     | No       | S3/MinIO access key                             |
| `S3_SECRET_ACCESS_KEY` | No       | S3/MinIO secret key                             |
| `S3_ENDPOINT`          | No       | S3 endpoint URL (e.g. `http://localhost:9000`)  |
| `S3_BUCKET`            | No       | S3 bucket name (default: `lobehub`)             |
| `OPENAI_API_KEY`       | No       | Default OpenAI API key                          |
| `DEBUG`                | No       | Enable debug mode + API docs (default: `false`) |

### 3. Set up the database

```bash
# Run Alembic migrations
alembic upgrade head
```

### 4. Start the server

```bash
# Development (auto-reload)
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0"}
```

API docs (when `DEBUG=true`):

- Swagger UI: <http://localhost:8000/api/docs>
- ReDoc: <http://localhost:8000/api/redoc>

## Project Structure

```
python-backend/
├── main.py                  # App entry point
├── alembic/                 # Database migrations
├── app/
│   ├── config.py            # Settings (pydantic-settings)
│   ├── auth.py              # JWT/OIDC validation
│   ├── db.py                # Async SQLAlchemy engine
│   ├── dependencies.py      # FastAPI deps (auth, admin)
│   ├── feature_flags.py     # Feature flag resolution
│   ├── admin.py             # Admin endpoints
│   ├── models/              # SQLModel table definitions (75 tables)
│   ├── routers/             # API route handlers
│   │   ├── config.py        # GET /api/config
│   │   ├── agents.py        # Agent CRUD
│   │   ├── sessions.py      # Session CRUD + groups
│   │   ├── topics.py        # Topic CRUD
│   │   ├── messages.py      # Message CRUD
│   │   ├── chat.py          # SSE streaming chat
│   │   ├── files.py         # File upload/manage
│   │   ├── knowledge.py     # Knowledge base CRUD + search
│   │   ├── memory.py        # Memory CRUD + search
│   │   ├── tools.py         # Manual tool execution
│   │   ├── plugins.py       # Plugin install/uninstall
│   │   ├── skills.py        # Skill CRUD
│   │   └── ai_infra.py      # AI provider/model config
│   ├── services/            # Business logic
│   │   ├── llm_service.py   # LiteLLM wrapper
│   │   ├── file_service.py  # S3 + DB file records
│   │   ├── knowledge_service.py  # KB + chunking + embedding
│   │   ├── memory_service.py     # 5-layer memory + vector search
│   │   ├── chat_service.py       # RAG + memory + streaming
│   │   ├── tool_execution.py     # Tool dispatch
│   │   ├── mcp_service.py        # MCP client
│   │   └── skill_engine.py       # Agent context resolution
│   ├── tools/               # Builtin tool definitions
│   │   ├── registry.py      # @register decorator + schema gen
│   │   ├── calculator.py    # Math eval
│   │   ├── memory_tool.py   # Memory search/store
│   │   ├── knowledge_base_tool.py  # KB search
│   │   └── agent_builder.py       # Agent CRUD tools
│   └── skills/              # Builtin skill definitions
│       └── builtin.py       # Artifacts, Web Search, KB skills
└── pyproject.toml           # Dependencies
```

## API Endpoints

| Prefix                 | Endpoints | Description                    |
| ---------------------- | --------- | ------------------------------ |
| `/api/config`          | 1         | Server config + feature flags  |
| `/api/agents`          | 7         | Agent CRUD + KB links          |
| `/api/sessions`        | 9         | Session + group CRUD           |
| `/api/topics`          | 6         | Topic CRUD + batch delete      |
| `/api/messages`        | 8         | Message CRUD + batch ops       |
| `/api/chat`            | 1         | SSE streaming chat             |
| `/api/files`           | 6         | File upload/manage             |
| `/api/knowledge-bases` | 9         | KB CRUD + file assoc + search  |
| `/api/memories`        | 6         | Memory CRUD + search           |
| `/api/tools`           | 2         | List + manual run              |
| `/api/plugins`         | 4         | Install/uninstall plugins      |
| `/api/skills`          | 7         | Skill CRUD + search            |
| `/api/ai-infra`        | —         | AI provider/model config       |
| `/api/admin`           | 7         | User management + system stats |
| `/api/health`          | 1         | Health check                   |

## Auth

Authentication uses OIDC JWT tokens (Keycloak recommended). Set `AUTH_OIDC_ISSUER` to enable.
When unset, auth is disabled (development mode).

Users are auto-provisioned on first API call from JWT claims (`sub`, `email`, `preferred_username`).

Admin endpoints require the `admin` realm role in the JWT.

## Keycloak Setup

1. Create a realm (e.g. `lobehub`)
2. Create a client `lobehub-backend` (confidential, service account enabled)
3. Create a realm role `admin` and assign to admin users
4. Set `AUTH_OIDC_ISSUER=https://keycloak.example.com/realms/lobehub`
