# Ethos Python Backend MVP — Development Plan

## Overview

Port of Ethos's core backend to Python using FastAPI, SQLModel, Alembic, and Keycloak.

**Stack:** FastAPI + SQLModel + Alembic + litellm + Keycloak (OIDC) + PostgreSQL (pgvector) + S3/MinIO

**Auth:** Keycloak handles all authentication — no local auth tables needed in the app layer. JWT validation + auto-provisioning only.

---

## Phase 1: Database Models (ALL 72 tables — excludes auth tables)

Auth-related tables (`auth_sessions`, `accounts`, `verifications`, `two_factor`, `passkey`, `nextauth_*`, `oidc_*`, `oauth_handoffs`) are **skipped** — Keycloak owns identity. That removes 20 tables, leaving **72 tables** to define as SQLModel classes.

### 1.1 Core Models (MVP service code)

- [x] `models/user.py` — `users`, `user_settings`, `user_installed_plugins` (3 tables)
- [x] `models/agent.py` — `agents`, `agents_knowledge_bases`, `agents_files` (3 tables)
- [x] `models/session.py` — `sessions`, `session_groups` (2 tables)
- [x] `models/message.py` — `messages`, `message_plugins`, `messages_files`, `message_queries`, `message_query_chunks` (5 tables)
- [x] `models/topic.py` — `topics` (1 table)
- [x] `models/file.py` — `global_files`, `files`, `documents` (3 tables)
- [x] `models/knowledge.py` — `knowledge_bases`, `knowledge_base_files` (2 tables)
- [x] `models/rag.py` — `chunks`, `embeddings`, `document_chunks` (3 tables)
- [x] `models/ai_infra.py` — `ai_providers`, `ai_models` (2 tables)
- [x] `models/memory.py` — `user_memories`, `user_memories_preferences`, `user_memories_contexts`, `user_memories_activities`, `user_memories_identities`, `user_memories_experiences` (6 tables)
- [x] `models/skill.py` — `agent_skills` (1 table)
- [x] `models/rbac.py` — `rbac_roles`, `rbac_permissions`, `rbac_role_permissions`, `rbac_user_roles` (4 tables)

### 1.2 Non-MVP Models (schema only, no service code yet)

- [x] `models/chat_group.py` — `chat_groups`, `chat_groups_agents` (2 tables)
- [x] `models/message_ext.py` — `message_groups`, `message_tts`, `message_translates`, `message_chunks` (4 tables)
- [x] `models/topic_ext.py` — `threads`, `topic_documents`, `topic_shares` (3 tables)
- [x] `models/document_ext.py` — `document_histories` (1 table)
- [x] `models/rag_ext.py` — `unstructured_chunks` (1 table)
- [x] `models/rag_eval.py` — `rag_eval_datasets`, `rag_eval_dataset_records`, `rag_eval_evaluations`, `rag_eval_evaluation_records` (4 tables)
- [x] `models/task.py` — `tasks`, `task_dependencies`, `task_documents`, `task_topics`, `briefs`, `task_comments` (6 tables)
- [x] `models/agent_ops.py` — `agent_bot_providers`, `agent_cron_jobs`, `agent_documents` (3 tables)
- [x] `models/agent_eval.py` — `agent_eval_benchmarks`, `agent_eval_datasets`, `agent_eval_test_cases`, `agent_eval_runs`, `agent_eval_run_topics` (5 tables)
- [x] `models/generation.py` — `generation_topics`, `generation_batches`, `generations` (3 tables)
- [x] `models/persona.py` — `user_memory_persona_documents`, `user_memory_persona_document_histories` (2 tables)
- [x] `models/misc.py` — `async_tasks`, `api_keys`, `notifications`, `notification_deliveries` (4 tables)

### 1.3 Infrastructure

- [x] `models/__init__.py` — Re-export all models
- [x] `models/_helpers.py` — Shared mixins: `TimestampMixin`, `id_generator()`, pgvector column type
- [x] `db.py` — AsyncSession engine + sessionmaker
- [x] `alembic/` — Initial migration with all tables + pgvector extension

---

## Phase 2: Auth & Config

- [x] `config.py` — Pydantic Settings (DB URL, Keycloak, S3, OpenAI, etc.)
- [x] `auth.py` — Keycloak JWT validation dependency (`get_current_user`)
- [x] `dependencies.py` — `get_or_create_user` auto-provisioning from JWT claims
- [x] `feature_flags.py` — Feature flag system (env-based, `FEATURE_FLAGS` string)

---

## Phase 3: AI Infrastructure (Model Selector)

- [x] `services/ai_infra_service.py` — Provider/model merge, runtime state, resolve provider
- [x] `services/model_catalog.py` — Builtin provider + model seed data (19 providers, 16 models)
- [x] `services/key_vault.py` — AES-256-GCM encrypt/decrypt (wire-compatible with TS KeyVaultsGateKeeper)
- [x] `routers/ai_infra.py` — Provider CRUD (8 endpoints) + Model CRUD (9 endpoints) + Runtime (1 endpoint) = 18 total

---

## Phase 4: Core Services

- [x] `services/llm_service.py` — litellm wrapper (chat + embeddings + credential resolution)
- [x] `services/file_service.py` — S3 client + DB record CRUD with global_files dedup
- [x] `services/knowledge_service.py` — KB CRUD, chunk creation, embedding, pgvector search
- [x] `services/memory_service.py` — 5-layer CRUD + vector search (summary/details)
- [x] `services/chat_service.py` — Core chat loop (RAG + memory injection + streaming)
- [x] `services/tool_execution.py` — Builtin tool registry + MCP fallback dispatch
- [x] `services/mcp_service.py` — MCP client (stdio + SSE transports, JSON-RPC)
- [x] `services/skill_engine.py` — System prompt assembly + tool schema collection + KB resolution

---

## Phase 5: Routers

- [x] `routers/config.py` — `GET /api/config` (feature flags + server config) — 1 endpoint
- [x] `routers/agents.py` — Agent CRUD + KB link/unlink — 7 endpoints
- [x] `routers/sessions.py` — Session CRUD + Session Group CRUD — 9 endpoints
- [x] `routers/topics.py` — Topic CRUD + batch delete — 6 endpoints
- [x] `routers/messages.py` — Message CRUD + batch ops + file links — 8 endpoints
- [x] `routers/chat.py` — SSE streaming chat with RAG + memory + tool schemas — 1 endpoint
- [x] `routers/files.py` — Upload, presigned URL, record, list, get, delete — 6 endpoints
- [x] `routers/knowledge.py` — KB CRUD, file assoc, vector search — 9 endpoints
- [x] `routers/memory.py` — Memory CRUD + text search — 6 endpoints
- [x] `routers/tools.py` — List builtins + manual run — 2 endpoints
- [x] `routers/plugins.py` — Install / update / uninstall / list — 4 endpoints

---

## Phase 6: Tools & Skills

- [x] `tools/registry.py` — Tool registry with OpenAI function-calling schemas
- [x] `tools/calculator.py` — Safe math expression eval (AST-based)
- [x] `tools/memory_tool.py` — memory_search + memory_store tools
- [x] `tools/knowledge_base_tool.py` — knowledge_base_search tool
- [x] `tools/agent_builder.py` — 5 tools: create, update, delete, list, get
- [x] `skills/builtin.py` — 3 builtin skills: Artifacts, Web Search, Knowledge Base
- [x] `routers/skills.py` — Skill CRUD + search + builtin merge (7 endpoints)

---

## Phase 7: Admin & Final Integration

- [x] `admin.py` — Admin endpoints: user CRUD, user stats, system stats (7 endpoints, admin-gated)
- [x] `main.py` — App assembly: 14 routers, CORS, lifespan, global error handler, health check
- [x] S3 wrapper already in `services/file_service.py` (Phase 4)
- [x] `pyproject.toml` — All dependencies with versions (Phase 1)
- [x] `README.md` — Setup guide (prerequisites, env vars, Keycloak, project structure)
- [x] `.env.example` — Annotated environment template

---

## Phase 8: Critical Gaps (SPA-blocking)

### 8a. User Router — SPA boot payload + settings

- [x] `routers/user.py` — `getUserState` (initial boot payload: settings, preference, guide, onboarding, flags)
- [x] `routers/user.py` — `updateSettings`, `resetSettings`
- [x] `routers/user.py` — `updateAvatar` (upload to S3, delete old)
- [x] `routers/user.py` — `updatePreference`, `updateGuide`, `makeUserOnboarded`
- [x] `routers/user.py` — `updateUsername`, `updateFullName`

### 8b. Chat tool-call loop (multi-round)

- [x] `services/chat_service.py` — Full tool-call loop (non-streaming): LLM → detect tool_calls → execute → feed results → re-call (max 10 rounds)
- [x] `services/tool_execution.py` — `execute_tool_call_with_context`: injects session+user_id for memory/KB/agent tools

### 8c. Thread Router — conversation branching

- [x] `routers/threads.py` — Thread CRUD (create, list by topic, get, update, delete) + get thread messages
- [x] `models/message.py` — Added `thread_id` FK + index

### 8d. Document & Chunk CRUD

- [x] `routers/documents.py` — List docs, get, update, delete (cascades chunks/embeddings), list doc chunks, doc stats
- [x] `routers/chunks.py` — Get chunk, update, delete, vector search

### 8e. Import/Export

- [x] `routers/importer.py` — Import from JSON file (agents, sessions, topics, messages with ID remapping)
- [x] `routers/exporter.py` — Export all as JSON, export session as Markdown or JSON

---

## Phase 9: Important Gaps

- [x] `routers/notifications.py` — List / mark-read / mark-all-read / dismiss (4 endpoints)
- [x] `routers/api_keys.py` — List / create / delete personal API keys (3 endpoints)
- [x] `routers/search.py` — Unified ILIKE search across messages, topics, agents
- [x] `routers/share.py` — Create/get/delete shareable conversation links (3 endpoints)
- [x] `routers/generation.py` — Text generation + image generation via LiteLLM (2 endpoints)
- [x] `routers/agent_groups.py` — Group CRUD + assign/remove agent (6 endpoints)

---

## Phase 10: Important Features

### 10a. Home & Sidebar

- [x] `routers/home.py` — `getSidebarAgentList` (pinned/recent agents for sidebar), `searchAgents`, `updateAgentSessionGroupId`

### 10b. Recent Items

- [x] `routers/recent.py` — `getAll` (last N topics/documents/tasks with route paths for quick-switch UI)

### 10c. Upload (S3 pre-signed URLs)

- [x] `routers/upload.py` — `createS3PreSignedUrl` (client-side direct upload to S3)

### 10d. User Memory (structured)

- [x] `routers/user_memory.py` — Rich user memory system: identity, preferences, experiences, activities, contexts, stats (16 endpoints)
- [ ] `services/memory_extraction.py` — LLM-driven extraction from conversations into structured memory layers (deferred)

### 10e. Notebook (topic → document)

- [x] `routers/notebook.py` — Create/update/delete documents linked to topics (markdown/note/report)
- [x] Topic-document association: bind conversation outputs to editable documents

### 10f. Agent Documents (VFS)

- [x] `routers/agent_documents.py` — Agent-scoped file/document CRUD (SOUL.md, plan files, skill docs) (6 endpoints)
- [ ] `services/agent_document_vfs.py` — Virtual filesystem abstraction for agent documents (deferred)

### 10g. Follow-up Actions

- [x] `routers/follow_up.py` — Extract suggested follow-up actions from conversation context via LLM

### 10h. Usage & Analytics

- [x] `routers/usage.py` — Token/cost tracking: `findByMonth`, `findAndGroupByDay`, `findAndGroupByDateRange` (3 endpoints)
- [x] Derived from existing Message model (input_tokens, output_tokens, token_count)

### 10i. Marketplace

- [x] `routers/market.py` — Browse/search community agents, install/uninstall from market (3 endpoints)
- [ ] Market skill import (from URL/GitHub/zip) (deferred)

### 10j. Session Groups

- [x] `routers/session_groups.py` — Session group CRUD + assign/remove session (6 endpoints)

### 10k. Streaming Tool Loop

- [x] `services/chat_service.py` — Streaming mode tool-call loop (accumulate tool_calls from stream → execute → re-stream)
- [x] Async generator yields chunks to client, tool execution happens between stream rounds

---

## Phase 12: MCP Full Feature Set

### 12a. MCPService Rewrite

- [x] `services/mcp_service.py` — Full `MCPService` class (singleton) with:
  - Client connection pool (keyed by serialized params)
  - `initialize` handshake (JSON-RPC `initialize` method)
  - `list_tools(params)` → list of tool schemas (with retry)
  - `list_raw_tools(params)` → raw MCP tool objects
  - `list_resources(params)` → MCP resources
  - `list_prompts(params)` → MCP prompts
  - `call_tool(params, tool_name, args, process_content_blocks)` → processed result
  - `get_streamable_manifest(identifier, url, metadata, auth, headers)` → manifest
  - `get_stdio_manifest(params, metadata)` → manifest
  - Streamable HTTP + stdio transport support

### 12b. Content Processor

- [x] `services/mcp_content_processor.py` — Process MCP tool result content blocks:
  - Image blocks: base64 → S3 upload → proxy URL
  - Audio blocks: base64 → S3 upload → proxy URL
  - `content_blocks_to_string()` — text/image/audio/resource to markdown

### 12c. MCP Router

- [x] `routers/mcp.py` — HTTP endpoints for MCP operations (7 endpoints):
  - `GET /api/mcp/tools` — listTools (HTTP params)
  - `GET /api/mcp/tools/raw` — listRawTools
  - `GET /api/mcp/resources` — listResources
  - `GET /api/mcp/prompts` — listPrompts
  - `POST /api/mcp/tools/call` — callTool (with content processing)
  - `POST /api/mcp/manifest/http` — getStreamableMcpServerManifest
  - `POST /api/mcp/manifest/stdio` — getStdioMcpServerManifest

### 12d. Integration

- [x] Wire MCP router in `main.py`
- [x] Update `tool_execution.py` to use new `MCPService` singleton (supports both dict params and legacy clients)

---

## Phase 15: Critical Builtin Tools

Implements 9 production-quality builtin tools to replace stubs and complete the memory system.

### 15a. Config & Dependencies

- [x] `config.py` — Add `search_provider`, `tavily_api_key`, `searxng_url`, `serper_api_key`, `code_interpreter_enabled`, `code_interpreter_timeout`
- [x] `pyproject.toml` — Add `simpleeval`, `beautifulsoup4`
- [x] `.env.example` — Add Web Search + Code Interpreter sections

### 15b. Tool Implementations (`services/builtin_tools.py`)

- [x] `web_search` — Real search via Tavily / SearXNG / Serper with auto-detect from available keys
- [x] `url_crawler` — Fetch URL + extract readable content (BeautifulSoup, strip nav/scripts)
- [x] `calculator` — Safe math evaluation via `simpleeval` (trig, log, constants)
- [x] `topic_reference` — Fetch topic summary or recent messages (DB context)
- [x] `dalle_image_gen` — OpenAI DALL-E image generation (dall-e-3, size/quality params)
- [x] `code_interpreter` — Sandboxed Python subprocess with timeout + restricted env
- [x] `user_interaction` — Ask clarifying questions (structured for LangGraph interrupt)
- [x] `memory_search` — Vector similarity search with layer/category/limit filters, relevance scoring
- [x] `memory_store` — 5-layer memory creation with auto-embedding (event/semantic/episodic/procedural/persona)
- [x] `BUILTIN_TOOL_SCHEMAS` — 9 OpenAI function-calling schemas for LLM tool discovery

### 15c. Skills, Skill Store, Activator (`services/builtin_tools.py`)

- [x] `skills` executor — `findAll`, `findByName`, `readResource`, `runCommand` (sandbox), `execScript` (multi-lang sandbox)
- [x] `skill_store` — `searchSkill` (Ethos market API + local fallback), `importFromUrl`, `importFromGitHub`, `importFromMarket`
- [x] `activator` — `activateTools` (resolve manifests from user/builtin skills, track activated set), `activateSkill` (single-skill shorthand)
- [x] `BUILTIN_TOOL_SCHEMAS` — 11 new schemas for skills/store/activator APIs (double-underscore naming)

### 15d. Dispatcher Rewrite (`services/tool_execution.py`)

- [x] Refactor to import from `builtin_tools.py` (no more inline registry/stubs)
- [x] Context-aware routing for `memory_search`, `memory_store`, `topic_reference`
- [x] Context-aware routing for `skills__*`, `skill_store__*`, `activator__*` (double-underscore dispatch)
- [x] `activated_tool_ids` param passed through to activator for per-operation state
- [x] `get_builtin_tool_schemas()` API for injecting tool schemas into LLM calls

---

## Phase 14: Agent Runtime (LangGraph + Langfuse)

Replaces the monolithic chat-loop with a step-based agent execution engine using LangGraph for state management/orchestration and Langfuse for tracing.

### 14a. Dependencies & Config

- [x] Add `langgraph`, `langchain-core`, `langgraph-checkpoint-postgres`, `langfuse` to `pyproject.toml`
- [x] `config.py` — Add Langfuse config fields (`langfuse_public_key`, `langfuse_secret_key`, `langfuse_host`, `langfuse_enabled`) + Agent Runtime fields
- [x] `.env` / `.env.example` — Add Langfuse + Agent Runtime env vars

### 14b. Agent Runtime Service (LangGraph)

- [x] `services/agent_runtime.py` — Core agent runtime:
  - `AgentState` (TypedDict): messages, status, step_count, usage, cost, error, metadata, pending_tool_calls, human_input
  - `AgentGraph` builder: LangGraph `StateGraph` with nodes:
    - `llm_node` — calls litellm via existing `llm_service.chat()`, tracks usage/cost
    - `tool_node` — dispatches tool calls via existing `tool_execution.py`
    - `human_review_node` — `interrupt()` for tool approval (human-in-the-loop)
    - `context_node` — RAG + memory injection via existing `chat_service.build_context()`
  - Conditional edges: after LLM → tool_calls? → human_review (if configured) → tools → LLM; no tool_calls → END
  - Langfuse `CallbackHandler` wired into LangGraph execution for full tracing
  - `AsyncPostgresSaver` checkpointer for state persistence (reuses DATABASE_URL)
  - Operation management: `create_operation()`, `run_operation()`, `get_status()`, `interrupt()`, `resume_with_tool_result()`, `resume_with_human_input()`

### 14c. Agent Router (HTTP API)

- [x] `routers/agent.py` — Agent execution endpoints (8 endpoints):
  - `POST /api/agent` — Create operation (+ optional auto-stream)
  - `POST /api/agent/run` — Run operation (non-streaming)
  - `GET /api/agent/stream` — SSE event stream by operationId
  - `GET /api/agent/status/{operation_id}` — Poll operation status
  - `POST /api/agent/interrupt/{operation_id}` — Interrupt running operation
  - `POST /api/agent/tool-result` — Submit approved/rejected tool result (human-in-the-loop)
  - `GET /api/agent/operations` — List user operations
  - `DELETE /api/agent/{operation_id}` — Cleanup operation

### 14d. Integration

- [x] Wire agent router in `main.py`
- [x] Existing `routers/chat.py` remains for simple chat (backward compat)
- [x] Agent runtime uses existing services: `llm_service`, `tool_execution`, `chat_service.build_context`, `mcp_service`

---

## Phase 13: Testing

- [ ] Unit tests for models (create, query, delete)
- [ ] Unit tests for services (mock DB)
- [ ] Integration tests for routers (TestClient)
- [ ] Auth tests (Keycloak JWT mock)
- [ ] E2E: chat with tool calling flow

---

## Effort Estimate

| Phase                               | Effort (AI-assisted) |
| ----------------------------------- | -------------------: |
| Phase 1: Models (72 tables)         |                   8h |
| Phase 2: Auth & Config              |                   3h |
| Phase 3: AI Infra (Model Selector)  |                   6h |
| Phase 4: Core Services              |                  20h |
| Phase 5: Routers                    |                   8h |
| Phase 6: Tools & Skills             |                   5h |
| Phase 7: Admin & Integration        |                   4h |
| Phase 8: Critical Gaps              |                  12h |
| Phase 9: Important Gaps             |                   6h |
| Phase 10: Important Features        |                  24h |
| Phase 12: MCP Full Feature Set      |                   8h |
| Phase 14: Agent Runtime (LangGraph) |                  16h |
| Phase 15: Builtin Tools (12 tools)  |                  10h |
| Phase 13: Testing                   |                   8h |
| **Total**                           |           **\~136h** |

---

## Current Status

**Phase 15 COMPLETE — Builtin Tools + Skills/Store/Activator** (12 tools, 20 schemas, 197 total routes, 38 routers)

Phase 1: 26 model files, 74 tables, Alembic migration.
Phase 2: config.py, auth.py, dependencies.py, feature_flags.py.
Phase 3: key_vault.py, model_catalog.py, ai_infra_service.py, routers/ai_infra.py.
Phase 4: llm_service.py, file_service.py, knowledge_service.py, memory_service.py,
chat_service.py, tool_execution.py, mcp_service.py, skill_engine.py.
Phase 5: config, agents, sessions, topics, messages, chat, files, knowledge,
memory, tools, plugins routers (59 endpoints).
Phase 6: Tool registry (9 tools), builtin skills (3), skills router (7 endpoints).
Phase 7: admin.py (7 endpoints), main.py (app assembly).
Phase 8: user router (9 endpoints), chat tool loop, threads (6), documents (6),
chunks (4), importer (1), exporter (3). tool_execution context injection.
Phase 9: notifications (4), api_keys (3), search (1), share (3), generation (2),
agent_groups (6).
Phase 10: home (3), recent (1), upload (1), user_memory (16), notebook (5),
agent_documents (6), follow_up (1), usage (3), market (3), session_groups (6),
streaming tool loop in chat_service.
Phase 12: mcp_service.py rewrite (MCPService singleton, HTTP+stdio transports,
initialize handshake, connection pool, retry), mcp_content_processor.py
(image/audio S3 upload, contentBlocksToString), routers/mcp.py (7 endpoints),
tool_execution.py MCPService integration.

Phase 14: agent_runtime.py (LangGraph StateGraph with context/llm/tools/human_review nodes,
AsyncPostgresSaver checkpointer, Langfuse tracing), routers/agent.py (8 endpoints),
config.py + .env + .env.example (Langfuse + Agent Runtime config).

Phase 15: builtin_tools.py (12 tools), tool_execution.py rewrite:

- 9 core tools: web_search, url_crawler, calculator, topic_reference, dalle_image_gen,
  code_interpreter, user_interaction, memory_search, memory_store.
- 3 skill tools: skills (findAll/findByName/readResource/runCommand/execScript),
  skill_store (searchSkill/importFromUrl/importFromGitHub/importFromMarket),
  activator (activateTools/activateSkill).
- 20 BUILTIN_TOOL_SCHEMAS (OpenAI function-calling format, double-underscore naming for sub-APIs).
- tool_execution.py: double-underscore dispatch, activated_tool_ids per-operation state.

Next: Phase 13 (Testing — unit, integration, auth, E2E). Deferred items: memory_extraction service, agent_document_vfs service.
