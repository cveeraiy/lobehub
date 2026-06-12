# Cross-Stack E2E Functional Test Plan

## Overview

This plan covers end-to-end functional tests that exercise the **full stack**:
TS SPA frontend → Hono server (TRPC) → Python FastAPI backend → PostgreSQL.

The existing `e2e/` suite uses **Cucumber + Playwright** (browser-driven, BDD).
The existing `python-backend/tests/e2e/` suite uses **pytest + httpx** (API-only).

This plan bridges them: browser-driven scenarios where the frontend UI triggers
TRPC calls that are fulfilled by the Python backend, verifying the data round-trips
correctly across the camelCase ↔ snake_case boundary.

---

## Architecture Under Test

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Playwright)                                       │
│  SPA: React + Zustand + SWR + @trpc/client (superjson)      │
└──────────────────┬──────────────────────────────────────────┘
                   │  TRPC queries/mutations (camelCase, superjson)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Hono Server (TS)                                           │
│  - TRPC router layer (src/server/routers/lambda/)           │
│  - callPythonBackend() proxy (X-Service-Token + userId)     │
│  - Better Auth session management                           │
└──────────────────┬──────────────────────────────────────────┘
                   │  REST API (snake_case JSON)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Python FastAPI Backend                                     │
│  - TRPC adapter (app/trpc/adapter.py) — handles /trpc/…    │
│  - REST routers (app/routers/*.py) — handles /api/…         │
│  - Keycloak JWT or Service Token auth                       │
└──────────────────┬──────────────────────────────────────────┘
                   │  asyncpg
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL (shared database)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Infrastructure (Docker Compose)

| Service    | Port | Notes                                |
| ---------- | ---- | ------------------------------------ |
| PostgreSQL | 5433 | Shared by TS and Python backends     |
| Keycloak   | 8080 | OIDC provider (realm: `lobehub`)     |
| TS (Hono)  | 3006 | SPA + TRPC router + Python proxy     |
| Python     | 8000 | FastAPI with TRPC adapter + REST API |

### Environment Variables (TS Server)

```
DATABASE_URL=postgresql://postgres:lobechat@localhost:5433/lobehub
PYTHON_BACKEND_URL=http://localhost:8000
PYTHON_BACKEND_SERVICE_TOKEN=<shared-secret>
AUTH_SECRET=e2e-test-secret-key-for-better-auth-32chars!
KEY_VAULTS_SECRET=LA7n9k3JdEcbSgml2sxfw+4TV1AzaaFU5+R176aQz4s=
```

### Environment Variables (Python Server)

```
DATABASE_URL=postgresql+asyncpg://postgres:lobechat@localhost:5433/lobehub
SERVICE_TOKEN=<shared-secret>  # must match PYTHON_BACKEND_SERVICE_TOKEN
ENABLE_MOCK_DEV_USER=0
```

### Test User

| Provider    | Username               | Password         |
| ----------- | ---------------------- | ---------------- |
| Better Auth | <e2e-test@lobehub.com> | TestPassword123! |
| Keycloak    | chandra                | test123          |

---

## Test Phases

### Phase 1: Infrastructure & Health (P0, Smoke)

| ID         | Scenario                                                  | Verifies                      |
| ---------- | --------------------------------------------------------- | ----------------------------- |
| XSTACK-001 | Python backend `/health` returns 200                      | Python server is alive        |
| XSTACK-002 | TS server `/chat` returns 200                             | Hono server + SPA served      |
| XSTACK-003 | TRPC `healthcheck` via Python adapter returns "i'm live!" | TS→Python TRPC adapter wiring |
| XSTACK-004 | Login via Better Auth and get session cookie              | Auth stack works              |
| XSTACK-005 | Python `/trpc/lambda/healthcheck` returns OK              | Python TRPC adapter directly  |

### Phase 2: User State Round-Trip (P0)

The SPA fetches `user.getUserState` on load — this is the first TRPC call after login.

| ID         | Scenario                                    | Verifies                             |
| ---------- | ------------------------------------------- | ------------------------------------ |
| XSTACK-010 | After login, sidebar shows user avatar/name | getUserState TRPC → Python → DB      |
| XSTACK-011 | Update username via settings UI             | updateUsername mutation round-trip   |
| XSTACK-012 | Update user settings (language, theme)      | updateSettings mutation → DB persist |
| XSTACK-013 | Verify settings persist after page reload   | Full state round-trip                |

### Phase 3: Session & Agent CRUD via UI (P0)

| ID         | Scenario                                  | Verifies                        |
| ---------- | ----------------------------------------- | ------------------------------- |
| XSTACK-020 | Create new session from sidebar           | session.createSession mutation  |
| XSTACK-021 | Session appears in sidebar after creation | getGroupedSessions query        |
| XSTACK-022 | Rename session via context menu           | updateSession mutation          |
| XSTACK-023 | Delete session via context menu           | removeSession mutation          |
| XSTACK-024 | Create session group                      | sessionGroup.createSessionGroup |
| XSTACK-025 | Move session to group                     | updateSession with groupId      |

### Phase 4: Topic CRUD via Chat (P0)

| ID         | Scenario                                | Verifies                             |
| ---------- | --------------------------------------- | ------------------------------------ |
| XSTACK-030 | Send first message → auto-creates topic | message.createMessage + topic.create |
| XSTACK-031 | Topic appears in topic list             | topic.getTopics query                |
| XSTACK-032 | Rename topic via context menu           | topic.updateTopic mutation           |
| XSTACK-033 | Delete topic                            | topic.removeTopic mutation           |
| XSTACK-034 | Topic count badge updates               | topic.countTopics query              |

### Phase 5: Message CRUD via Chat (P0)

| ID         | Scenario                           | Verifies                    |
| ---------- | ---------------------------------- | --------------------------- |
| XSTACK-040 | Send message and see it in chat    | createMessage → getMessages |
| XSTACK-041 | Edit user message                  | updateMessage mutation      |
| XSTACK-042 | Delete message                     | removeMessage mutation      |
| XSTACK-043 | Messages persist after page reload | Full message round-trip     |
| XSTACK-044 | Message ordering is chronological  | getMessages sort order      |

### Phase 5b: Multi-Turn Conversation (P0)

Verifies conversation history context carries across multiple exchanges.

| ID         | Scenario                                              | Verifies                            |
| ---------- | ----------------------------------------------------- | ----------------------------------- |
| XSTACK-045 | Send 3 messages in sequence, all visible in chat      | Message list ordering & persistence |
| XSTACK-046 | Conversation history sent to agent on each turn       | Context window includes prior msgs  |
| XSTACK-047 | Navigate away and back, conversation fully restored   | getMessages returns full history    |
| XSTACK-048 | Clear conversation, verify empty state in both stacks | removeAllMessages + UI empty state  |

### Phase 5c: Thread / Branch Replies (P1)

Verifies thread creation and message branching within a topic.

| ID         | Scenario                                         | Verifies                                  |
| ---------- | ------------------------------------------------ | ----------------------------------------- |
| XSTACK-055 | Create thread from an existing message           | POST /api/threads + messages.thread_id FK |
| XSTACK-056 | Send message inside a thread                     | createMessage with thread_id              |
| XSTACK-057 | Thread messages appear separately from main chat | getMessages filtered by thread_id         |
| XSTACK-058 | Delete thread, verify messages cleaned up        | removeThread cascade                      |
| XSTACK-059 | Thread count badge shows correct number          | thread.getThreads query                   |

### Phase 5d: Regenerate / Retry Response (P1)

Verifies response regeneration and retry flows.

| ID         | Scenario                                               | Verifies                      |
| ---------- | ------------------------------------------------------ | ----------------------------- |
| XSTACK-060 | Regenerate AI response replaces last assistant message | updateMessage + re-exec agent |
| XSTACK-061 | Retry after error produces new response                | Error recovery → execAgent    |
| XSTACK-062 | Regenerated response visible in chat immediately       | Optimistic UI + DB persist    |
| XSTACK-063 | Original response is replaced, not duplicated          | Message count stays same      |

### Phase 6: Agent Execution via Python Proxy (P1)

The TS router delegates `ai-agent/exec` to the Python backend via `PythonAgentProxyService`.

| ID         | Scenario                                       | Verifies                   |
| ---------- | ---------------------------------------------- | -------------------------- |
| XSTACK-070 | Send message to default agent, get AI response | execAgent TS→Python proxy  |
| XSTACK-071 | AI response streams tokens into chat bubble    | streamExecAgent SSE proxy  |
| XSTACK-072 | Error handling: Python backend returns 400     | Error propagation TS→SPA   |
| XSTACK-073 | Error handling: Python backend is down         | 502 error shown gracefully |

### Phase 7: Agent Management via REST (P1)

These use Python REST endpoints directly (not TRPC).

| ID         | Scenario                      | Verifies                  |
| ---------- | ----------------------------- | ------------------------- |
| XSTACK-080 | Create custom agent via UI    | POST /api/agents          |
| XSTACK-081 | Agent appears in sidebar list | Agent data visible in SPA |
| XSTACK-082 | Update agent system prompt    | PUT /api/agents/:id       |
| XSTACK-083 | Delete agent                  | DELETE /api/agents/:id    |

### Phase 8: Settings & AI Provider Config (P1)

| ID         | Scenario                                     | Verifies                     |
| ---------- | -------------------------------------------- | ---------------------------- |
| XSTACK-090 | Open settings → provider tab loads providers | config.getGlobalConfig query |
| XSTACK-091 | Add AI provider key via settings             | Key vault encrypt/store      |
| XSTACK-092 | Provider model list loads after key saved    | AI infra endpoints           |

### Phase 8b: Feature Flags (P1)

Feature flags are parsed from the `FEATURE_FLAGS` env var by **both** stacks and served
to the SPA via `config.getGlobalConfig` (TRPC) and `GET /api/config` (REST).
Both backends must produce identical `FeatureFlagsState` for the same env input.

#### 8b-i: Default Flags & Config Endpoint

| ID         | Scenario                                               | Verifies                      |
| ---------- | ------------------------------------------------------ | ----------------------------- |
| XSTACK-093 | GET /api/config returns featureFlags with defaults     | Python config router defaults |
| XSTACK-094 | TRPC config.getGlobalConfig returns serverFeatureFlags | Python TRPC adapter defaults  |
| XSTACK-095 | Default flags match between TS schema and Python       | Cross-stack default parity    |

#### 8b-ii: Env Override Parsing

| ID         | Scenario                                              | Verifies                |
| ---------- | ----------------------------------------------------- | ----------------------- |
| XSTACK-096 | FEATURE_FLAGS="+market" enables showMarket            | Single flag enable      |
| XSTACK-097 | FEATURE_FLAGS="-knowledge_base" disables KB           | Single flag disable     |
| XSTACK-098 | FEATURE_FLAGS="+market,-changelog" handles multi-flag | Comma-separated parsing |
| XSTACK-099 | Invalid flag names are silently ignored               | Robustness              |

#### 8b-iii: Enterprise Mode

| ID         | Scenario                                             | Verifies                     |
| ---------- | ---------------------------------------------------- | ---------------------------- |
| XSTACK-0A0 | enterprise_mode=true hides provider settings         | showProvider=false           |
| XSTACK-0A1 | enterprise_mode=true hides market/changelog/ai_image | Consumer features suppressed |
| XSTACK-0A2 | enterprise_mode=true forces hideGitHub=true          | Commercial branding          |

#### 8b-iv: UI Visibility Cross-Check

| ID         | Scenario                                            | Verifies               |
| ---------- | --------------------------------------------------- | ---------------------- |
| XSTACK-0A3 | knowledge_base flag disabled → KB UI hidden in SPA  | Flag→UI mapping works  |
| XSTACK-0A4 | admin_panel enabled → admin link visible in sidebar | Flag→UI mapping works  |
| XSTACK-0A5 | market enabled → discover page accessible           | Flag→route guard works |

### Phase 9: User Memory System (P2)

The memory system has **6 layers** served by two routers:

- `/api/user-memory` — structured memory CRUD (base + identities + preferences)
- `/api/memories` — memory service with semantic search

#### 9a: Base Memory CRUD

| ID         | Scenario                                       | Verifies                            |
| ---------- | ---------------------------------------------- | ----------------------------------- |
| XSTACK-100 | Create base memory with title/summary/details  | POST /api/user-memory (201)         |
| XSTACK-101 | Get memory by ID                               | GET /api/user-memory/:id            |
| XSTACK-102 | Update memory title and status                 | PUT /api/user-memory/:id            |
| XSTACK-103 | List memories with layer filter                | GET /api/user-memory?layer=semantic |
| XSTACK-104 | List memories with category filter             | GET /api/user-memory?category=...   |
| XSTACK-105 | List memories with pagination (limit + offset) | Pagination params work              |
| XSTACK-106 | Delete memory                                  | DELETE /api/user-memory/:id         |
| XSTACK-107 | Get non-existent memory returns 404            | Error handling                      |

#### 9b: Identity Layer

| ID         | Scenario                                   | Verifies                               |
| ---------- | ------------------------------------------ | -------------------------------------- |
| XSTACK-110 | Create identity with type/description/role | POST /api/user-memory/identities       |
| XSTACK-111 | Create identity with relationship field    | Relationship field persists            |
| XSTACK-112 | List identities returns created entries    | GET /api/user-memory/identities        |
| XSTACK-113 | Delete identity by ID                      | DELETE /api/user-memory/identities/:id |
| XSTACK-114 | Deleted identity no longer in list         | List after delete is clean             |

#### 9c: Preference Layer

| ID         | Scenario                                     | Verifies                                |
| ---------- | -------------------------------------------- | --------------------------------------- |
| XSTACK-115 | Create preference with conclusion_directives | POST /api/user-memory/preferences       |
| XSTACK-116 | Create preference with suggestions and tags  | All fields persist correctly            |
| XSTACK-117 | List preferences                             | GET /api/user-memory/preferences        |
| XSTACK-118 | Delete preference                            | DELETE /api/user-memory/preferences/:id |

#### 9d: Stats Across All Layers

| ID         | Scenario                                          | Verifies                            |
| ---------- | ------------------------------------------------- | ----------------------------------- |
| XSTACK-120 | Stats returns zero counts on fresh user           | GET /api/user-memory/stats baseline |
| XSTACK-121 | Create items across layers, stats counts increase | Stats reflects all 6 layer counts   |
| XSTACK-122 | Delete items, stats counts decrease               | Stats accurately tracks deletions   |

#### 9e: Memory Search (via /api/memories)

| ID         | Scenario                                     | Verifies                         |
| ---------- | -------------------------------------------- | -------------------------------- |
| XSTACK-125 | Create memory via /api/memories              | POST /api/memories (201)         |
| XSTACK-126 | List memories via /api/memories              | GET /api/memories                |
| XSTACK-127 | Filter memories by layer (semantic/episodic) | GET /api/memories?layer=semantic |
| XSTACK-128 | Search memories by text query                | POST /api/memories/search        |
| XSTACK-129 | Delete memory via /api/memories/:id          | DELETE /api/memories/:id         |

#### 9f: Cross-Stack Memory Verification

| ID         | Scenario                                              | Verifies                       |
| ---------- | ----------------------------------------------------- | ------------------------------ |
| XSTACK-130 | Memory created via Python API visible in TS TRPC      | Data round-trip across stacks  |
| XSTACK-131 | Memory created via TS frontend persists in Python API | Reverse direction verification |
| XSTACK-132 | User isolation: user A cannot see user B's memories   | Auth + user_id scoping         |

### Phase 10: Skills & Agent Tool Binding (P1)

Skills define agent capabilities — each has a prompt template and optional tool schemas.
The skill engine resolves these at runtime into the LLM's system prompt and `tools` parameter.

#### 10a: Skill CRUD

| ID         | Scenario                                   | Verifies                           |
| ---------- | ------------------------------------------ | ---------------------------------- |
| XSTACK-200 | Create skill with name/description/content | POST /api/skills (201)             |
| XSTACK-201 | Get skill by ID                            | GET /api/skills/:id                |
| XSTACK-202 | Get skill by identifier                    | GET /api/skills/by-identifier/:id  |
| XSTACK-203 | Update skill manifest                      | PUT /api/skills/:id                |
| XSTACK-204 | Delete skill                               | DELETE /api/skills/:id             |
| XSTACK-205 | List user skills                           | GET /api/skills?source=user        |
| XSTACK-206 | Search skills by name/description          | GET /api/skills/search/query?q=... |

#### 10b: Builtin Skills

| ID         | Scenario                                          | Verifies                       |
| ---------- | ------------------------------------------------- | ------------------------------ |
| XSTACK-207 | List includes builtin skills                      | GET /api/skills (merged list)  |
| XSTACK-208 | Filter builtin-only skills                        | GET /api/skills?source=builtin |
| XSTACK-209 | Get builtin skill by identifier                   | Fallback to BUILTIN_SKILLS     |
| XSTACK-20A | User skill overrides builtin with same identifier | User skill shadows builtin     |

#### 10c: Agent ↔ Skill Binding & Skill Engine

| ID         | Scenario                                             | Verifies                              |
| ---------- | ---------------------------------------------------- | ------------------------------------- |
| XSTACK-20B | Create agent with skill identifiers in plugins array | Agent.plugins stores skill refs       |
| XSTACK-20C | Resolve agent context includes skill prompts         | build_system_prompt() merges skills   |
| XSTACK-20D | Resolve agent context includes skill tool schemas    | collect_tool_schemas() extracts tools |
| XSTACK-20E | Agent with KB binding returns kb_ids                 | resolve_agent_context() junction      |
| XSTACK-20F | Execute agent with skill → tool call in response     | Full exec flow with skill tools       |

### Phase 11: MCP Server Integration (P1)

MCP (Model Context Protocol) connects agents to external tool servers.
Only HTTP transport is supported in web environments; stdio is blocked.

#### 11a: MCP Discovery

| ID         | Scenario                            | Verifies                    |
| ---------- | ----------------------------------- | --------------------------- |
| XSTACK-210 | List tools from HTTP MCP server     | POST /api/mcp/tools         |
| XSTACK-211 | List raw tools from HTTP MCP server | POST /api/mcp/tools/raw     |
| XSTACK-212 | List resources from HTTP MCP server | POST /api/mcp/resources     |
| XSTACK-213 | List prompts from HTTP MCP server   | POST /api/mcp/prompts       |
| XSTACK-214 | Get HTTP MCP server manifest        | POST /api/mcp/manifest/http |

#### 11b: MCP Tool Execution

| ID         | Scenario                                       | Verifies                      |
| ---------- | ---------------------------------------------- | ----------------------------- |
| XSTACK-215 | Call tool on HTTP MCP server                   | POST /api/mcp/tools/call      |
| XSTACK-216 | Tool call with S3 content processing           | Content block upload pipeline |
| XSTACK-217 | Tool call with invalid tool name returns error | Error handling                |

#### 11c: MCP Security

| ID         | Scenario                                      | Verifies                |
| ---------- | --------------------------------------------- | ----------------------- |
| XSTACK-218 | Stdio MCP type returns 400 in web environment | Security: stdio blocked |
| XSTACK-219 | HTTP MCP without url returns 400              | Validation              |
| XSTACK-21A | MCP requires auth (no anonymous access)       | Auth enforcement        |

### Phase 12: Plugin System (P2)

Plugins are user-installed extensions (MCP-based or custom) with per-user settings.

| ID         | Scenario                                             | Verifies                           |
| ---------- | ---------------------------------------------------- | ---------------------------------- |
| XSTACK-220 | Install plugin with identifier and manifest          | POST /api/plugins/install (201)    |
| XSTACK-221 | List installed plugins                               | GET /api/plugins                   |
| XSTACK-222 | Update plugin settings                               | PUT /api/plugins/:identifier       |
| XSTACK-223 | Uninstall plugin                                     | DELETE /api/plugins/:identifier    |
| XSTACK-224 | Plugin with custom_params persists correctly         | custom_params round-trip           |
| XSTACK-225 | Agent with plugin → tools available during execution | Plugin tools in agent exec context |

### Phase 13: Builtin Tools (P2)

| ID         | Scenario                                 | Verifies            |
| ---------- | ---------------------------------------- | ------------------- |
| XSTACK-226 | List builtin tools                       | GET /api/tools      |
| XSTACK-227 | Run builtin tool by name                 | POST /api/tools/run |
| XSTACK-228 | Run tool with invalid name returns error | Error handling      |

### Phase 13b: Human-in-the-Loop (P1)

The Python backend supports human-in-the-loop via two independent mechanisms:

1. **Agent Runtime** (`/api/agent`) — LangGraph `interrupt()` pauses at
   `human_review_node` when `require_human_approval=true`. The user
   approves/rejects via `POST /api/agent/tool-result`.
2. **AI Agent Service** (`/api/ai-agent/exec`) — `resume=true` +
   `resume_approval` body field. Three decisions: `approved`,
   `rejected`, `rejected_continue`. Persisted to `MessagePlugin`.

#### 13b-i: Agent Runtime HITL (`/api/agent`)

| ID         | Scenario                                                         | Verifies                                      |
| ---------- | ---------------------------------------------------------------- | --------------------------------------------- |
| XSTACK-240 | Create operation with `require_human_approval=true`              | POST /api/agent + flag accepted               |
| XSTACK-241 | Operation pauses at human_review_node → status=waiting_for_human | GET /api/agent/status/:id `needs_human_input` |
| XSTACK-242 | SSE stream emits `human_intervention` event with pending tools   | GET /api/agent/stream event type              |
| XSTACK-243 | Approve tool call → operation resumes and completes              | POST /api/agent/tool-result `approved=true`   |
| XSTACK-244 | Reject tool call → LLM receives rejection reason                 | POST /api/agent/tool-result `approved=false`  |
| XSTACK-245 | Reject with custom reason → reason included in LLM context       | `reason` field round-trip                     |
| XSTACK-246 | Submit tool-result on non-waiting operation → 400                | Error guard                                   |
| XSTACK-247 | Submit tool-result on unknown operation → 404                    | Error guard                                   |

#### 13b-ii: AI Agent Service HITL (`/api/ai-agent/exec`)

| ID         | Scenario                                                             | Verifies                             |
| ---------- | -------------------------------------------------------------------- | ------------------------------------ |
| XSTACK-248 | Resume exec with `resume=true` + `resume_approval.decision=approved` | Approved tool call executes          |
| XSTACK-249 | Resume with `decision=rejected` → tool call skipped                  | Rejection persisted to MessagePlugin |
| XSTACK-24A | Resume with `decision=rejected_continue` → agent continues           | Soft rejection flow                  |
| XSTACK-24B | Resume without `parent_message_id` → 400/500                         | Validation: required field           |
| XSTACK-24C | Resume with `parent_message_id` pointing at non-tool msg → error     | Validation: role must be 'tool'      |
| XSTACK-24D | `tool_call_id` mismatch → error                                      | Validation: stored vs requested      |

#### 13b-iii: Interrupt Running Task

| ID         | Scenario                                                    | Verifies                            |
| ---------- | ----------------------------------------------------------- | ----------------------------------- |
| XSTACK-24E | Interrupt running operation via `/api/agent/interrupt/:id`  | POST interrupt → status=interrupted |
| XSTACK-24F | Interrupt via `/api/ai-agent/interrupt` with `thread_id`    | Thread-based interrupt              |
| XSTACK-250 | Interrupt via `/api/ai-agent/interrupt` with `operation_id` | Operation-based interrupt           |
| XSTACK-251 | Interrupt already-finished operation → 400                  | Terminal state guard                |
| XSTACK-252 | SSE stream emits `interrupted` event on abort               | Event type                          |

#### 13b-iv: User Interaction Tool (Builtin)

| ID         | Scenario                                            | Verifies                                      |
| ---------- | --------------------------------------------------- | --------------------------------------------- |
| XSTACK-253 | Run `user_interaction` tool with question           | POST /api/tools/run returns structured prompt |
| XSTACK-254 | Run `user_interaction` with `type=select` + options | Options included in response                  |
| XSTACK-255 | Run `user_interaction` without question → error     | Validation                                    |

#### 13b-v: Config-Driven HITL

| ID         | Scenario                                                       | Verifies                       |
| ---------- | -------------------------------------------------------------- | ------------------------------ |
| XSTACK-256 | `AGENT_REQUIRE_HUMAN_APPROVAL=true` env → all operations pause | Global config flag             |
| XSTACK-257 | Per-operation `require_human_approval` overrides global config | Explicit flag > config default |

### Phase 13c: Skill Sharing & Access Control (P1) — ✅ IMPLEMENTED

> **Backend implementation complete.** The following schema & endpoints were added:
>
> - `visibility` column on `agent_skills` (`private` | `public` | `restricted`)
> - `agent_skill_shares` junction table (`skill_id`, `shared_with_user_id`)
> - `POST /api/skills/{id}/share` — share with specific users
> - `POST /api/skills/{id}/unshare` — revoke shares
> - `GET /api/skills/{id}/shares` — list share records (owner only)
> - `PUT /api/skills/{id}/visibility` — change visibility (owner only)
> - Updated `list_skills`, `get_skill`, `search_skills` to include public/shared skills
> - Authorization guards: only owner can update/delete/share/change visibility
>
> **Test file:** `python-backend/tests/e2e/test_24_skill_sharing.py` (21 tests)
> **Requires:** Two Keycloak test users (User A + User B)

#### 13c-i: Visibility Defaults & Validation

| ID         | Scenario                                              | Verifies                      |
| ---------- | ----------------------------------------------------- | ----------------------------- |
| XSTACK-260 | Create skill without visibility → defaults to private | Default field value           |
| XSTACK-261 | Create skill with visibility=public                   | Explicit visibility on create |
| XSTACK-262 | Create skill with invalid visibility → 400            | Input validation              |

#### 13c-ii: Visibility Update

| ID         | Scenario                                  | Verifies         |
| ---------- | ----------------------------------------- | ---------------- |
| XSTACK-263 | PUT /{id}/visibility changes value        | Endpoint works   |
| XSTACK-264 | PUT /{id}/visibility with bad value → 400 | Input validation |
| XSTACK-265 | Set visibility=private clears all shares  | Cascade cleanup  |

#### 13c-iii: Private Skill Isolation

| ID         | Scenario                                       | Verifies       |
| ---------- | ---------------------------------------------- | -------------- |
| XSTACK-266 | Private skill invisible to User B (GET + list) | User isolation |

#### 13c-iv: Public Skill Visibility

| ID         | Scenario                                       | Verifies                 |
| ---------- | ---------------------------------------------- | ------------------------ |
| XSTACK-267 | Public skill visible to User B (GET + list)    | Cross-user public access |
| XSTACK-268 | Owner's public skill not in source=shared list | Source label correctness |

#### 13c-v: Restricted Sharing

| ID         | Scenario                                            | Verifies                     |
| ---------- | --------------------------------------------------- | ---------------------------- |
| XSTACK-269 | Share restricted skill → User B can access          | Cross-user restricted access |
| XSTACK-26A | Share private skill auto-upgrades to restricted     | Auto-visibility promotion    |
| XSTACK-26B | Restricted skill with no shares invisible to User B | No shares = no access        |
| XSTACK-26C | List shares returns shared users                    | Share record listing         |
| XSTACK-26D | Duplicate share is idempotent                       | Upsert behavior              |
| XSTACK-26E | Share with self is skipped                          | Self-share guard             |

#### 13c-vi: Unshare

| ID         | Scenario                      | Verifies         |
| ---------- | ----------------------------- | ---------------- |
| XSTACK-26F | Unshare → User B loses access | Share revocation |

#### 13c-vii: Authorization Guards

| ID         | Scenario                           | Verifies                 |
| ---------- | ---------------------------------- | ------------------------ |
| XSTACK-270 | Non-owner cannot update skill      | Owner-only update        |
| XSTACK-271 | Non-owner cannot delete skill      | Owner-only delete        |
| XSTACK-272 | Non-owner cannot share skill       | Owner-only share         |
| XSTACK-273 | Non-owner cannot change visibility | Owner-only visibility    |
| XSTACK-274 | Non-owner cannot list shares       | Owner-only share listing |

#### 13c-viii: Search & Cascade

| ID         | Scenario                                   | Verifies                   |
| ---------- | ------------------------------------------ | -------------------------- |
| XSTACK-275 | Search finds public skill (cross-user)     | Search includes public     |
| XSTACK-276 | Search excludes private skill (cross-user) | Search respects visibility |
| XSTACK-277 | Delete skill cascades share records        | FK CASCADE delete          |

### Phase 14: Task & Brief System (P2)

| ID         | Scenario            | Verifies                  |
| ---------- | ------------------- | ------------------------- |
| XSTACK-300 | Create task via API | POST /api/tasks           |
| XSTACK-301 | Update task status  | Task status state machine |
| XSTACK-302 | Create brief        | POST /api/briefs          |
| XSTACK-303 | List briefs         | GET /api/briefs           |

### Phase 15: Knowledge Base & VFS (P2)

| ID         | Scenario                                  | Verifies                  |
| ---------- | ----------------------------------------- | ------------------------- |
| XSTACK-310 | Create knowledge base                     | POST /api/knowledge-bases |
| XSTACK-311 | VFS: create folder, write file, read file | VFS CRUD operations       |
| XSTACK-312 | VFS: rename, copy, delete                 | VFS file management       |

### Phase 16: Share & Usage (P3)

| ID         | Scenario              | Verifies                |
| ---------- | --------------------- | ----------------------- |
| XSTACK-320 | Share a topic         | POST /api/share         |
| XSTACK-321 | View shared topic     | GET /api/share/:id      |
| XSTACK-322 | Usage stats by month  | GET /api/usage/by-month |
| XSTACK-323 | Create/delete API key | API key lifecycle       |

### Phase 17: Cron Jobs & Agent Signal (P3)

| ID         | Scenario                  | Verifies                        |
| ---------- | ------------------------- | ------------------------------- |
| XSTACK-330 | Create cron job for agent | POST /api/agent-cron-jobs       |
| XSTACK-331 | Register signal policy    | POST /api/agent-signal/policies |
| XSTACK-332 | Emit signal               | POST /api/agent-signal/emit     |

---

## Test Implementation Strategy

### Hybrid Approach

Each test scenario uses **one or both** of these approaches depending on what it verifies:

1. **Browser-driven (Cucumber + Playwright)** — for UI-visible behavior
   - Login, navigation, visual state, user interactions
   - Verifies the full round-trip from browser → TS → Python → DB → Python → TS → browser

2. **API-driven (pytest + httpx)** — for backend-only behavior
   - Direct REST/TRPC calls to the Python backend
   - Verifies the Python backend independently
   - Already complete: 166 passing tests in `python-backend/tests/e2e/`

3. **Mixed-mode (new)** — browser + API verification
   - Perform action in browser, then verify via direct API call (or vice versa)
   - Example: Create session in UI → verify via `GET /api/sessions` on Python backend
   - Example: Create agent via Python API → verify it appears in SPA sidebar

### File Structure

```
e2e/src/
├── features/
│   └── cross-stack/                    # NEW: cross-stack features
│       ├── health.feature              # Phase 1
│       ├── user-state.feature          # Phase 2
│       ├── session-crud.feature        # Phase 3
│       ├── topic-crud.feature          # Phase 4
│       ├── message-crud.feature        # Phase 5
│       ├── multi-turn.feature          # Phase 5b
│       ├── thread-replies.feature      # Phase 5c
│       ├── regenerate-retry.feature    # Phase 5d
│       ├── agent-execution.feature     # Phase 6
│       └── agent-management.feature    # Phase 7
├── steps/
│   └── cross-stack/                    # NEW: step definitions
│       ├── health.steps.ts
│       ├── user-state.steps.ts
│       ├── session.steps.ts
│       ├── topic.steps.ts
│       ├── message.steps.ts
│       ├── conversation.steps.ts
│       ├── thread.steps.ts
│       ├── agent.steps.ts
│       └── api-helpers.ts             # Direct Python API call helper
└── support/
    └── pythonBackend.ts               # NEW: httpx-like helper for Python API
```

### API Helper Pattern

The mixed-mode tests need a helper to call the Python backend directly from
the Cucumber step definitions (TypeScript):

```typescript
// e2e/src/support/pythonBackend.ts

const PYTHON_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';
const SERVICE_TOKEN = process.env.PYTHON_BACKEND_SERVICE_TOKEN || '';

export async function callPython(
  path: string,
  userId: string,
  opts: { method?: string; body?: unknown } = {},
) {
  const { method = 'GET', body } = opts;
  const res = await fetch(`${PYTHON_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Service-Token': SERVICE_TOKEN,
      'X-Internal-User-Id': userId,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, data: await res.json() };
}
```

### Sample Cucumber Feature (Phase 2)

```gherkin
@cross-stack @user-state
Feature: User state round-trip (TS SPA → Python Backend)
  As a logged-in user
  I want my user state to persist across the full stack
  So that my settings and preferences are consistent

  Background:
    Given the user is logged in

  @XSTACK-010 @P0 @smoke
  Scenario: User state loads after login
    When I navigate to the home page
    Then the sidebar should show the user's name
    And the Python backend should have the user in the database

  @XSTACK-011 @P0
  Scenario: Update username persists across stacks
    Given I navigate to "/settings/profile"
    When I update my username to "e2e_updated_user"
    And I reload the page
    Then the settings page should show username "e2e_updated_user"
    And the Python backend user record should have username "e2e_updated_user"
```

### Sample Step Definition

```typescript
// e2e/src/steps/cross-stack/user-state.steps.ts
import { Given, When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import { CustomWorld } from '../../support/world';
import { callPython } from '../../support/pythonBackend';
import { TEST_USER } from '../../support/seedTestUser';

Then('the Python backend should have the user in the database', async function (this: CustomWorld) {
  const { status, data } = await callPython(`/trpc/lambda/user.getUserState`, TEST_USER.id);
  expect(status).toBe(200);
  expect(data.result.data).toBeDefined();
});

Then(
  'the Python backend user record should have username {string}',
  async function (this: CustomWorld, username: string) {
    const { status, data } = await callPython(`/trpc/lambda/user.getUserState`, TEST_USER.id);
    expect(status).toBe(200);
    expect(data.result.data.username).toBe(username);
  },
);
```

---

## Running the Cross-Stack Tests

### Quick Start

```bash
# 1. Start infrastructure (Docker: Postgres + Keycloak)
docker compose -f docker-compose/dev/docker-compose.yml up -d

# 2. Start Python backend
cd python-backend && .venv/bin/uvicorn main:app --port 8000 &

# 3. Start TS server (with Python proxy enabled)
PYTHON_BACKEND_URL=http://localhost:8000 bun run dev:spa &

# 4. Run cross-stack tests
cd e2e
BASE_URL=http://localhost:3006 \
  PYTHON_BACKEND_URL=http://localhost:8000 \
  bun run test -- --tags "@cross-stack"
```

### npm Scripts (add to e2e/package.json)

```json
{
  "scripts": {
    "test:cross-stack": "cucumber-js --config cucumber.config.js --tags '@cross-stack'",
    "test:cross-stack:smoke": "cucumber-js --config cucumber.config.js --tags '@cross-stack and @smoke'"
  }
}
```

---

## Data Integrity Checks

Cross-stack tests should verify **data consistency** across the boundary:

| Check                        | How                                                         |
| ---------------------------- | ----------------------------------------------------------- |
| camelCase ↔ snake_case       | Create in UI (camelCase) → read via Python API (snake_case) |
| superjson Date serialization | Create with timestamp → verify ISO format in both stacks    |
| User ID consistency          | Better Auth userId == Keycloak sub == Python user_id        |
| FK integrity                 | Create parent in TS, child in Python → verify FK holds      |
| Concurrent writes            | Write from both stacks → verify no conflicts                |

---

## Test Priority Matrix

| Priority  | Phase                           | Count   | Automation Effort |
| --------- | ------------------------------- | ------- | ----------------- |
| P0        | Health & Auth                   | 5       | Low               |
| P0        | User State                      | 4       | Medium            |
| P0        | Session CRUD                    | 6       | Medium            |
| P0        | Topic CRUD                      | 5       | Medium            |
| P0        | Message CRUD                    | 5       | Medium            |
| P0        | Multi-Turn Conversation         | 4       | Medium            |
| P1        | Thread / Branch Replies         | 5       | Medium            |
| P1        | Regenerate / Retry              | 4       | High (LLM mock)   |
| P1        | Agent Execution                 | 4       | High (LLM mock)   |
| P1        | Agent Management                | 4       | Medium            |
| P1        | Settings/Provider               | 3       | Medium            |
| P1        | Feature Flags (8b)              | 13      | Medium            |
| P1        | Skills CRUD (10a)               | 7       | Low               |
| P1        | Builtin Skills (10b)            | 4       | Low               |
| P1        | Agent↔Skill Engine (10c)        | 5       | High (LLM mock)   |
| P1        | MCP Discovery (11a)             | 5       | Medium            |
| P1        | MCP Tool Exec (11b)             | 3       | Medium            |
| P1        | MCP Security (11c)              | 3       | Low               |
| P1        | HITL: Agent Runtime (13b-i)     | 8       | High (LLM mock)   |
| P1        | HITL: AI Agent Svc (13b-ii)     | 6       | High (LLM mock)   |
| P1        | HITL: Interrupt (13b-iii)       | 5       | Medium            |
| P1        | HITL: Interaction Tool (13b-iv) | 3       | Low               |
| P1        | HITL: Config-Driven (13b-v)     | 2       | Low               |
| P1        | Skill Sharing (13c)             | 21      | Medium            |
| P2        | Plugin System (12)              | 6       | Medium            |
| P2        | Builtin Tools (13)              | 3       | Low               |
| P2        | Memory: Base CRUD (9a)          | 8       | Low               |
| P2        | Memory: Identity (9b)           | 5       | Low               |
| P2        | Memory: Preference (9c)         | 4       | Low               |
| P2        | Memory: Stats (9d)              | 3       | Low               |
| P2        | Memory: Search (9e)             | 5       | Medium            |
| P2        | Memory: Cross-Stack (9f)        | 3       | Medium            |
| P2        | Task/Brief (14)                 | 4       | Low               |
| P2        | KB & VFS (15)                   | 3       | Medium            |
| P3        | Share & Usage (16)              | 4       | Low               |
| P3        | Cron & Signal (17)              | 3       | Low               |
| **Total** |                                 | **190** |                   |

---

## Implementation Order

1. **Week 1**: Phase 1 (Health) + Phase 2 (User State) — validates plumbing
2. **Week 2**: Phase 3 (Sessions) + Phase 4 (Topics) — core CRUD
3. **Week 3**: Phase 5 (Messages) + Phase 5b (Multi-Turn) — chat flow basics
4. **Week 4**: Phase 5c (Threads) + Phase 5d (Regenerate) + Phase 6 (Agent Exec) — advanced chat
5. **Week 5**: Phase 7-8b (Agent Mgmt + Settings + Feature Flags) — configuration
6. **Week 6**: Phase 10-11 (Skills + MCP) + Phase 13c (Skill Sharing) — agent tool ecosystem
7. **Week 7**: Phase 13b (HITL) — human-in-the-loop flows
8. **Week 8**: Phase 9 (Memory) + Phase 12-13 (Plugins + Tools) — extensions
9. **Week 9+**: Phase 14-17 — secondary features

---

## CI/CD Integration

```yaml
# .github/workflows/e2e-cross-stack.yml
name: Cross-Stack E2E
on:
  pull_request:
    paths:
      - 'src/server/**'
      - 'python-backend/**'
      - 'e2e/**'

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: paradedb/paradedb:latest
        ports: ['5433:5432']
        env:
          POSTGRES_PASSWORD: lobechat

    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2

      # Start Python backend
      - name: Start Python backend
        run: |
          cd python-backend
          pip install -r requirements.txt
          DATABASE_URL=postgresql+asyncpg://postgres:lobechat@localhost:5433/lobehub \
            uvicorn main:app --port 8000 &

      # Build and start TS server
      - name: Start TS server
        run: |
          bun install
          PYTHON_BACKEND_URL=http://localhost:8000 bun run build
          bun run start &

      # Run cross-stack E2E
      - name: Run tests
        run: |
          cd e2e && bun install && npx playwright install chromium
          BASE_URL=http://localhost:3006 \
            PYTHON_BACKEND_URL=http://localhost:8000 \
            bun run test:cross-stack
```
