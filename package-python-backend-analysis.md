# Packages vs Python Backend Analysis

Generated: 2026-05-19

This report classifies each top-level package under `packages/` and compares it with the in-repo FastAPI backend under `python-backend/`.

## Executive Summary

`packages/` is not a frontend-only or backend-only tree. It is a shared monorepo package layer:

- **Backend/server packages**: own database schemas/models, API/runtime logic, model provider calls, observability, OpenAPI/Hono services, and Node/Electron execution support.
- **Frontend/client packages**: render built-in tool UIs, inspector panes, portals, shared React components, and browser clients.
- **Shared/isomorphic packages**: contain constants, types, prompts, manifests, pure utilities, parsers, and protocol contracts used by both frontend and backend.

The Python backend is now a parallel backend implementation. Its strongest overlap is with:

- `packages/database`: Python SQLModel models mirror Drizzle-owned tables.
- `packages/agent-runtime`, `packages/agent-signal`, `packages/tool-runtime`, many `packages/builtin-tool-*`: Python has service/tool equivalents.
- `packages/model-runtime`, `packages/model-bank`, `packages/openapi`, `packages/fetch-sse`: Python has LLM, chat, webapi, and streaming equivalents.
- `packages/memory-user-memory`, `packages/file-loaders`, `packages/web-crawler`: Python has service/router/tool coverage for memory, files/RAG, and web search/crawling.

The key architectural rule is still: **TypeScript Drizzle in `packages/database` owns schema definition; Python SQLModel must match it.**

## Classification Legend

| Class    | Meaning                                                                                                    |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Backend  | Server/runtime/database/API code. Should be compared carefully with `python-backend`.                      |
| Frontend | React UI, render components, client display logic. Usually not ported to Python.                           |
| Shared   | Pure contracts, constants, manifests, data, utilities, or protocol code used across layers.                |
| Mixed    | Has both frontend UI and execution/runtime/server pieces. Python may need only the execution/runtime part. |
| Tool     | Built-in agent tool package. Often includes manifest + executor + optional client UI.                      |

## Package Inventory

| Package                            | Class                      | What It Contains                                                                                                    | Python Backend Comparison                                                                                                           |
| ---------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `agent-gateway-client`             | Shared/client              | Browser-compatible WebSocket client for Agent Gateway.                                                              | Python exposes agent execution/stream endpoints, but this package is a client/protocol helper, not backend logic.                   |
| `agent-manager-runtime`            | Backend/shared             | Agent create/update/runtime helpers used by agent builder/management tools.                                         | Compare with `app/services/ai_agent`, `app/services/system_agent`, and agent management routers.                                    |
| `agent-runtime`                    | Backend                    | Core TS agent execution, orchestration, intervention, audit, group orchestration.                                   | Direct overlap with `app/services/agent_runtime`, `agent_runtime_hooks`, `ai_agent`, and `app/routers/ai_agent.py`.                 |
| `agent-signal`                     | Backend/shared             | Agent Signal contracts and producer helpers.                                                                        | Direct overlap with `app/services/agent_signal` and `app/routers/agent_signal.py`.                                                  |
| `agent-templates`                  | Shared                     | Built-in template data.                                                                                             | Python may consume equivalent defaults, but no backend behavior to port.                                                            |
| `agent-tracing`                    | Backend/tooling            | Trace recorder/store/viewer/CLI types.                                                                              | Python has Langfuse/runtime tracing hooks; compare only if trace parity is required.                                                |
| `builtin-agents`                   | Shared/tool data           | Built-in agent definitions and tool bindings.                                                                       | Python has `app/services/system_agent` and built-in skill/tool registries; keep identifiers and defaults aligned.                   |
| `builtin-skills`                   | Shared/tool data           | Built-in skills/resources.                                                                                          | Python has `app/skills/builtin.py`; compare skill identifiers and resource payload expectations.                                    |
| `builtin-tool-activator`           | Mixed tool                 | Tool manifest, client UI, executor, execution runtime.                                                              | Python equivalent likely belongs in `app/tools/activator.py` and `tool_execution`. UI stays TS.                                     |
| `builtin-tool-agent-builder`       | Mixed tool                 | Agent builder manifest/client UI/executor.                                                                          | Compare executor semantics with agent creation/update APIs and `ai_agent` service.                                                  |
| `builtin-tool-agent-documents`     | Mixed tool                 | Agent document tool UI/executor/runtime.                                                                            | Strong overlap with `app/routers/agent_documents*.py`, `agent_document_vfs`, and `app/tools/agent_documents_tool.py`.               |
| `builtin-tool-agent-management`    | Mixed tool                 | Agent search/detail/update/call-agent UI and executor.                                                              | Strong overlap with `app/routers/agents.py`, `app/routers/ai_agent.py`, and `app/services/ai_agent`.                                |
| `builtin-tool-agent-marketplace`   | Mixed tool                 | Marketplace tool UI/runtime/executor.                                                                               | Compare with `app/routers/market.py` and `market_discover.py`.                                                                      |
| `builtin-tool-brief`               | Removed                    | Package removed; remaining TS manifest/identifier contract moved into `@lobechat/builtin-tools`.                    | Python has `app/routers/briefs.py`, `app/services/brief`, and `app/tools/brief_tool.py`.                                            |
| `builtin-tool-calculator`          | Removed                    | Package removed; remaining TS manifest and REST-backed executor contract moved into `@lobechat/builtin-tools`.      | Python `app/tools/calculator.py` owns calculator execution via SymPy/Pint.                                                          |
| `builtin-tool-claude-code`         | Frontend tool              | Claude Code tool render/client components.                                                                          | Mostly UI. Execution is likely external/heterogeneous agent side, not Python business API.                                          |
| `builtin-tool-cloud-sandbox`       | Mixed tool                 | Cloud sandbox UI, runtime, executor, local-system dependency.                                                       | Python has `app/routers/cloud_sandbox.py`; compare command execution contract and artifact upload behavior.                         |
| `builtin-tool-creds`               | Mixed tool                 | Credential tool UI/executor/runtime.                                                                                | Compare with Python key vault/API key/market credentials routes and `key_vault` service.                                            |
| `builtin-tool-cron`                | Removed                    | Package removed; remaining TS manifest/runtime/executor contract moved into `@lobechat/builtin-tools`.              | Python owns `app/routers/agent_cron_jobs.py` and task scheduler services.                                                           |
| `builtin-tool-group-agent-builder` | Mixed tool                 | Group-agent builder UI/runtime.                                                                                     | Compare with chat group and group-agent creation flows in Python.                                                                   |
| `builtin-tool-group-management`    | Mixed tool                 | Group task/agent management UI and executor.                                                                        | Compare with Python `chat_groups`, `ai_agent.exec-group`, and task services.                                                        |
| `builtin-tool-gtd`                 | Mixed tool                 | GTD/task tool UI, prompts, executor/runtime.                                                                        | Strong overlap with `app/routers/tasks.py`, `app/services/task`, and `app/tools/gtd_tool.py`.                                       |
| `builtin-tool-knowledge-base`      | Mixed tool                 | Knowledge-base tool UI/executor/runtime.                                                                            | Strong overlap with `app/routers/knowledge.py`, `chunks.py`, `files.py`, and `knowledge_service`.                                   |
| `builtin-tool-lobe-agent`          | Removed                    | Package removed; remaining TS visual-media manifest/runtime/executor contract moved into `@lobechat/builtin-tools`. | Python owns `app/tools/lobe_agent_tool.py` and `ai_agent` service.                                                                  |
| `builtin-tool-local-system`        | Mixed desktop tool         | Local desktop/system executor, IPC client UI, audit helpers.                                                        | Python backend does not own Electron local execution; only compare tool result contracts if routed through Python.                  |
| `builtin-tool-memory`              | Mixed tool                 | Memory tool UI/executor/runtime and prompts.                                                                        | Strong overlap with `app/routers/user_memory.py`, `app/services/memory_service`, and `app/tools/memory_tool.py`.                    |
| `builtin-tool-message`             | Mixed tool                 | Message tool UI/executor/runtime.                                                                                   | Compare with `app/routers/messages.py`, `chat.py`, and `chat_service`.                                                              |
| `builtin-tool-notebook`            | Mixed tool                 | Notebook UI/executor/runtime.                                                                                       | Compare with `app/routers/notebook.py` and `app/tools/notebook_tool.py`.                                                            |
| `builtin-tool-page-agent`          | Mixed tool                 | Page-agent editor/runtime integration.                                                                              | Compare with agent document/page agent APIs if Python handles execution; UI remains TS.                                             |
| `builtin-tool-remote-device`       | Backend/shared tool        | Remote device manifest/runtime.                                                                                     | Compare with device gateway APIs if Python participates; otherwise TS/client side.                                                  |
| `builtin-tool-skill-maintainer`    | Removed                    | Package and hidden TS built-in tool registration removed.                                                           | Python owns `/api/skill-maintainer/*` router coverage.                                                                              |
| `builtin-tool-skill-store`         | Mixed tool                 | Skill store UI/runtime/executor.                                                                                    | Strong overlap with `app/routers/skills.py`, `market_discover.py`, and `skill_engine`.                                              |
| `builtin-tool-skills`              | Mixed tool                 | Skill execution UI/runtime/executor.                                                                                | Strong overlap with `app/services/skill_engine` and `app/tools/skills.py`.                                                          |
| `builtin-tool-task`                | Removed                    | Package removed; remaining TS task manifest/list/executor contract moved into `@lobechat/builtin-tools`.            | Python owns `app/routers/tasks.py`, `app/services/task`, and `app/tools/task_tool.py`.                                              |
| `builtin-tool-topic-reference`     | Removed                    | Package removed; remaining TS manifest/identifier/executor wrapper moved into `@lobechat/builtin-tools`.            | Python has topic and message routers plus `app/tools/topic_reference.py`.                                                           |
| `builtin-tool-user-interaction`    | Mixed tool                 | Human interaction UI/executor/runtime.                                                                              | Compare with Python human-intervention flow in `ai_agent` router/service.                                                           |
| `builtin-tool-web-browsing`        | Mixed tool                 | Web browsing/search/crawl UI and runtime.                                                                           | Strong overlap with `app/routers/web_search.py`, `app/tools/web_search.py`, and `url_crawler.py`.                                   |
| `builtin-tool-web-onboarding`      | Removed                    | Package removed; remaining TS manifest/runtime utility/intervention contract moved into `@lobechat/builtin-tools`.  | Python owns onboarding REST/service document patch semantics and onboarding state endpoints.                                        |
| `builtin-tools`                    | Frontend/shared aggregator | Aggregates built-in tool renders, inspectors, portals, identifiers.                                                 | Mostly frontend registry. Python needs equivalent registry only for server-side tool execution.                                     |
| `chat-adapter-feishu`              | Backend/shared adapter     | Feishu/Lark chat SDK adapter.                                                                                       | Python has bot services/webhooks; compare platform payload conversion if porting bot runtime.                                       |
| `chat-adapter-line`                | Backend/shared adapter     | LINE chat SDK adapter.                                                                                              | Compare with Python bot platform support if porting.                                                                                |
| `chat-adapter-qq`                  | Backend/shared adapter     | QQ chat SDK adapter.                                                                                                | Compare with Python bot platform support if porting.                                                                                |
| `chat-adapter-wechat`              | Backend/shared adapter     | WeChat chat SDK adapter.                                                                                            | Compare with Python bot inbound/bridge services if porting.                                                                         |
| `config`                           | Shared                     | App config aggregation.                                                                                             | Python has `app/config.py`; compare env names/defaults only.                                                                        |
| `const`                            | Shared                     | Constants: protocol, messages, files, layout, hotkeys, RBAC, bot, etc.                                              | Python should align enum/string constants used on API boundaries, especially task, thread, bot, RBAC, and file values.              |
| `context-engine`                   | Backend/shared             | Context pipeline engine and processors.                                                                             | Python has context compression and agent runtime message handling; compare prompt/context assembly behavior.                        |
| `conversation-flow`                | Shared/frontend            | Conversation transformation/rendering engine and types.                                                             | Mostly UI/domain transformation. Python may need only persisted message/thread shape parity.                                        |
| `database`                         | Backend                    | Drizzle schemas, models, repositories, DB utilities.                                                                | Highest-priority comparison. Python models in `app/models` must mirror Drizzle schemas.                                             |
| `device-gateway-client`            | Shared/client              | WebSocket client for device gateway.                                                                                | Python does not appear to own device gateway server logic in this repo.                                                             |
| `edge-config`                      | Backend/shared             | Edge/business config access.                                                                                        | Compare with Python config/feature flags only where REST responses expose config.                                                   |
| `editor-runtime`                   | Shared/backend             | Editor runtime and prompts.                                                                                         | Compare only if Python executes page/document editing operations.                                                                   |
| `eval-dataset-parser`              | Backend/shared             | Parses CSV/XLSX/JSON/JSONL eval datasets.                                                                           | Strong overlap with `app/routers/agent_eval.py` and `rag_eval.py` dataset import/parse endpoints.                                   |
| `eval-rubric`                      | Backend/shared             | Rubric evaluator for agent eval benchmarks.                                                                         | Compare with Python agent evaluation services.                                                                                      |
| `fetch-sse`                        | Shared/client              | SSE fetch utilities and error parsing.                                                                              | Python must emit compatible streaming/event/error shapes for SPA clients.                                                           |
| `file-loaders`                     | Backend/shared             | File parsing/loaders and utility types.                                                                             | Strong overlap with Python file/chunk/RAG parse services and upload routes.                                                         |
| `heterogeneous-agents`             | Shared/client              | External agent adapter registry/config/client labels.                                                               | Compare with Python `agent_runtime` only if Python executes heterogeneous agents.                                                   |
| `local-file-shell`                 | Backend/desktop            | Local file/shell helpers built on file loaders.                                                                     | Mostly desktop/local. Python backend should not duplicate unless it owns local shell execution.                                     |
| `markdown-patch`                   | Shared                     | Markdown patch application utilities.                                                                               | Python may need parity only for onboarding/skills/page editing patch behavior.                                                      |
| `memory-user-memory`               | Backend/shared             | User memory extraction/conversion/providers/prompts/schemas.                                                        | Strong overlap with `app/services/memory_service` and `app/routers/user_memory.py`.                                                 |
| `model-bank`                       | Shared/backend             | Provider/model catalog and standard parameter definitions.                                                          | Strong overlap with `app/services/model_catalog`, `ai_infra_service`, and model/provider REST responses.                            |
| `model-runtime`                    | Backend                    | Provider runtime layer for LLM calls and errors.                                                                    | Strong overlap with `app/services/llm_service`, `provider_runtime.py`, `webapi.py`, image/video generation routes.                  |
| `observability-otel`               | Backend                    | OpenTelemetry helpers for node/trpc/gen-ai/modules.                                                                 | Python has Langfuse/runtime tracing; compare trace attributes only if cross-language observability must match.                      |
| `openapi`                          | Backend                    | Hono/OpenAPI controllers, routes, middleware, services.                                                             | Directly comparable with Python REST routers. Use for API parity checks.                                                            |
| `prompts`                          | Shared/backend             | Agent, chain, context, and tool prompts.                                                                            | Python services/tools should reuse or mirror prompt behavior where they replace TS execution.                                       |
| `python-interpreter`               | Shared/client/runtime      | Pyodide-based interpreter package.                                                                                  | Distinct from FastAPI backend; compare only for code-interpreter tool output contracts.                                             |
| `shared-tool-ui`                   | Frontend                   | Shared React UI for tool renders/inspectors.                                                                        | No Python port.                                                                                                                     |
| `ssrf-safe-fetch`                  | Backend/shared             | SSRF-safe fetch with browser/node conditional exports.                                                              | Python URL fetch/crawler/search code must enforce equivalent SSRF safety.                                                           |
| `tool-runtime`                     | Backend/shared             | Runtime abstractions for computer/tool execution.                                                                   | Strong overlap with Python `app/services/tool_execution` and `app/tools/*`.                                                         |
| `types`                            | Shared                     | Central TypeScript API/domain types.                                                                                | Python Pydantic request/response models must map to these contracts, with snake_case on REST boundary and camelCase in TS services. |
| `utils`                            | Shared/mixed               | Shared pure utilities plus `client` and `server` subexports.                                                        | Python should mirror only behavior that affects API contracts, IDs, parsing, serialization, pricing, cron, and safety.              |
| `web-crawler`                      | Backend/shared             | URL crawling, rules, SSRF-safe fetch integration.                                                                   | Strong overlap with `app/tools/url_crawler.py`, `web_search.py`, and web search routes.                                             |

## Python Backend Surface

The Python backend has:

- **Routers**: admin, agents, ai-agent, auth, bot, chat, chunks, config, files, generations, knowledge, market, memory, messages, notebook, sessions, skills, tasks, topics, usage, webapi, web-search, and other domain routers.
- **Services**: agent runtime, agent runtime hooks/types, agent signal, ai agent, bot, chat, context compression, file, knowledge, LLM, memory, model catalog/fallback, search, skill engine, task, tool execution.
- **Models**: SQLModel definitions for agents, messages, sessions, topics, files, documents, knowledge/RAG, eval, task, memory, AI infra, RBAC, users, notifications, generation, and agent ops.

## High-Priority Comparison Areas

### 1. Database Schema Parity

Compare `packages/database/src/schemas/*` and `packages/database/src/models/*` against `python-backend/app/models/*`.

Priority tables already mirrored in Python include:

- agents, agent files, agent knowledge bases
- agent bot providers, agent cron jobs, agent documents
- messages, message plugins/files/queries/chunks/groups/tts/translates
- sessions, session groups, topics, topic documents/shares, threads
- files, global files, documents, document histories
- knowledge bases, knowledge base files, chunks, embeddings, document chunks
- tasks, task dependencies/documents/topics/comments, briefs
- user memories, contexts, preferences, activities, identities, experiences
- agent eval and RAG eval tables
- users, user settings, accounts, installed plugins
- ai providers/models, API keys, async tasks, notifications, RBAC

Risk: schema drift causes Python 500s, FK failures, timestamp/type mismatches, or silent data shape bugs. Treat Drizzle as source of truth.

### 2. Runtime and Tool Execution Parity

Compare:

- TS: `agent-runtime`, `tool-runtime`, `builtin-tool-*`, `context-engine`, `prompts`
- Python: `app/services/agent_runtime`, `app/services/tool_execution`, `app/tools/*`, `app/services/context_compressor`

Important parity points:

- tool identifiers and manifest names
- input/output JSON schemas
- human-intervention semantics
- streaming event format
- task/thread status transitions
- prompt templates and system-role text
- error taxonomy and retry/interruption behavior

### 3. REST/OpenAPI Parity

Compare:

- TS: `packages/openapi`, `src/server/routers`, `src/app/(backend)/webapi`
- Python: `app/routers/*`

Important parity points:

- endpoint path and method
- request/response field casing
- auth dependency and service-token behavior
- pagination/list response shape
- SuperJSON wrapping for TRPC compatibility routes
- streaming and file upload behavior

### 4. Model Provider and Catalog Parity

Compare:

- TS: `model-runtime`, `model-bank`, `fetch-sse`
- Python: `llm_service`, `provider_runtime.py`, `model_catalog`, `model_fallback`, `webapi.py`

Important parity points:

- provider IDs and model IDs
- standard parameters and capability flags
- error mapping
- chat/image/video/TTS/STT routes
- SSE event format consumed by the SPA

### 5. Memory, RAG, Files, Search

Compare:

- TS: `memory-user-memory`, `file-loaders`, `web-crawler`, `eval-dataset-parser`, `eval-rubric`
- Python: `memory_service`, `file_service`, `knowledge_service`, `search`, `web_search`, `agent_eval`, `rag_eval`

Important parity points:

- extraction prompts and taxonomy values
- file parsing/chunking behavior
- vector/semantic search payloads
- evaluation dataset import behavior
- search provider result shape

## Backend vs Frontend Guidance

When deciding whether a `packages/*` package is backend or frontend, use these checks:

- If it imports React, antd, `@lobehub/ui`, or has `src/client`, it has frontend surface.
- If it has `executor`, `ExecutionRuntime`, provider calls, repositories, Drizzle, Hono, OpenTelemetry, or Node-only dependencies, it has backend/runtime surface.
- If it only exports constants, manifests, schemas, prompts, or types, treat it as shared and compare only boundary contracts.
- For mixed built-in tool packages, Python only needs parity for **executor/runtime/tool contract** behavior. The client render/inspector UI stays TypeScript.

## Suggested Next Audit

For a deeper parity report, generate three machine-readable matrices:

1. Drizzle table/column list vs SQLModel class/field list.
2. TS route/procedure/OpenAPI list vs Python router method/path list.
3. Built-in tool manifest/executor list vs Python `app/tools` registry list.

Those would reveal exact missing endpoints, schema drift, and tool contract drift beyond this package-level classification.
