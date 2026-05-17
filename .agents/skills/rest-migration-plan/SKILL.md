---
name: rest-migration-plan
description: Feature-by-feature TRPC→REST migration plan with dependency graph and E2E test requirements. Use when planning migration work, picking the next feature to migrate, checking dependencies, or writing E2E tests for a migrated feature. Triggers on 'migration plan', 'migration order', 'feature migration', 'e2e test', 'migration dependency', 'next feature to migrate'.
---

# REST Migration Plan — Feature by Feature

Each feature must be fully migrated (service `.rest.ts` → store imports from `.resolved` → direct `lambdaClient` calls removed) and validated with E2E tests before moving to the next.

## Dependency Graph

```
                        ┌─────────────┐
                   ┌────│  F0: Auth   │────┐
                   │    │  + Config   │    │
                   │    └─────────────┘    │
                   │           │           │
                   ▼           ▼           ▼
            ┌──────────┐ ┌──────────┐ ┌──────────┐
            │ F1: User │ │ F2: Home │ │F3: Global│
            │  State   │ │  + Nav   │ │  Config  │
            └──────────┘ └──────────┘ └──────────┘
                   │           │
          ┌────────┼───────────┼────────┐
          ▼        ▼           ▼        ▼
    ┌──────────┐┌──────────┐┌──────────┐┌──────────┐
    │F4: Agent ││F5: Sessn ││F6: Topic ││F7: Msgs  │
    │  CRUD    ││  CRUD    ││  CRUD    ││  CRUD    │
    └──────────┘└──────────┘└──────────┘└──────────┘
          │        │           │           │
          │        └─────┬─────┘           │
          │              ▼                 │
          │       ┌──────────┐             │
          ├──────>│ F8: Chat │<────────────┘
          │       │ Runtime  │
          │       └──────────┘
          │              │
    ┌─────┼──────────────┼─────────────┐
    ▼     ▼              ▼             ▼
┌──────┐┌──────┐  ┌───────────┐  ┌──────────┐
│F9:   ││F10:  │  │F11: Agent │  │F12: File │
│Brief ││Notif │  │  Docs/KB  │  │ Upload   │
└──────┘└──────┘  └───────────┘  └──────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │F13: RAG  │ │F14: Eval │ │F15: Tasks│
    │ Chunks   │ │ Bench    │ │ + Briefs │
    └──────────┘ └──────────┘ └──────────┘

    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │F16: Tools│ │F17: User │ │F18: AI   │
    │ Plugins  │ │ Memory   │ │ Infra    │
    │ Skills   │ │          │ │ Models   │
    └──────────┘ └──────────┘ └──────────┘

    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │F19: Disc │ │F20: Mark │ │F21: Admin│
    │ Discover │ │ Social   │ │          │
    └──────────┘ └──────────┘ └──────────┘

    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │F22: Bot  │ │F23:Klavis│ │F24: Cron │
    │ Msg      │ │ MCP      │ │ Jobs     │
    └──────────┘ └──────────┘ └──────────┘
```

---

## Feature Details

### F0: Auth + Config (Foundation — DONE)

**Python routers:** `auth.py`, `config.py`
**Frontend services:** `global.rest.ts`, `global.resolved.ts`
**Stores:** `store/serverConfig/action.ts`, `store/global/actions/general.ts`
**Direct lambdaClient:** None remaining

**What it covers:**

- `/api/auth/get-session` — session validation
- `/api/auth/sign-in/oauth2` — Keycloak OIDC login
- `/api/auth/callback/keycloak` — OIDC callback
- `/api/__server_config__` — SPA server config (feature flags, SSO providers)
- `/api/config/global` — global runtime config
- `/api/config/default-agent` — default agent config

**Status:** ✅ Complete — auth flow and config endpoints working.

**E2E Tests Required:**

```gherkin
@rest @auth @P0
Feature: Authentication via REST
  Scenario: User can sign in via Keycloak
  Scenario: Session cookie persists across page reload
  Scenario: Unauthenticated user is redirected to /signin
  Scenario: /api/__server_config__ returns disableEmailPassword=true
  Scenario: /api/__server_config__ returns oAuthSSOProviders=["keycloak"]
```

---

### F1: User State

**Depends on:** F0 (Auth)
**Python routers:** `user.py`
**Frontend services:** `user/index.rest.ts`, `user/resolved.ts`
**Stores:** `store/user/` (settings, profile, preferences, onboarding)
**Direct lambdaClient:** `layout/AuthProvider/MarketAuth/MarketAuthProvider.tsx` (5 calls)

**Key endpoints:**

- `GET /api/user/state` — user state (profile, settings, feature flags, onboarding)
- `PUT /api/user/settings` — update settings (general, language model, TTS)
- `PUT /api/user/profile` — update avatar, username, name
- `PUT /api/user/onboarding` — mark onboarding steps complete
- `GET /api/user/stats` — user statistics

**Migration work:**

1. ✅ `user/index.rest.ts` exists
2. ✅ `user/resolved.ts` exists
3. ⬜ Point `store/user` imports at resolved (verify already done)
4. ⬜ Migrate `MarketAuthProvider.tsx` lambdaClient calls → resolved service
5. ⬜ E2E tests

**E2E Tests Required:**

```gherkin
@rest @user @P0
Feature: User State via REST
  Scenario: App loads user state on startup (avatar, settings, feature flags)
  Scenario: User updates display name — persists after reload
  Scenario: User changes language model settings — persists after reload
  Scenario: User completes onboarding step — flag persists
  Scenario: Settings page renders all tabs without errors
```

---

### F2: Home + Navigation

**Depends on:** F0, F1
**Python routers:** `home.py`, `recent.py`
**Frontend services:** `home/index.rest.ts`, `home/resolved.ts`, `recent/index.rest.ts`, `recent/resolved.ts`
**Stores:** `store/home/`
**Direct lambdaClient:** None remaining in store

**Key endpoints:**

- `GET /api/home/sidebar` — sidebar agent list with groups
- `GET /api/recent` — recent conversations

**Migration work:**

1. ✅ `.rest.ts` + `resolved.ts` exist
2. ⬜ Verify store imports from resolved
3. ⬜ E2E tests

**E2E Tests Required:**

```gherkin
@rest @home @P0
Feature: Home Sidebar via REST
  Scenario: Sidebar loads agent list on startup
  Scenario: Sidebar shows pinned agents at top
  Scenario: Sidebar search filters agents by name
  Scenario: Creating a new agent adds it to the sidebar
  Scenario: Deleting an agent removes it from the sidebar
```

---

### F3: Global Config + Server Config

**Depends on:** F0
**Python routers:** `config.py`
**Frontend services:** `global.rest.ts`, `global.resolved.ts`
**Stores:** `store/serverConfig/action.ts`

**Status:** ✅ Mostly complete — TRPC compat endpoint at `/trpc/lambda/config.getGlobalConfig` still used.

**E2E Tests Required:**

```gherkin
@rest @config @P0
Feature: Global Config via REST
  Scenario: App fetches global config on startup without errors
  Scenario: Feature flags are applied (e.g., enableAgentMode)
  Scenario: OAuth SSO providers list is populated
```

---

### F4: Agent CRUD

**Depends on:** F1, F2
**Python routers:** `agents.py`, `agent_groups.py`
**Frontend services:** `agent.rest.ts`, `agent.resolved.ts`
**Stores:** `store/agent/slices/agent/action.ts`, `store/agent/slices/builtin/action.ts`, `store/home/slices/sidebarUI/action.ts`
**Direct lambdaClient:** None remaining in store (already uses resolved)

**Key endpoints:**

- `POST /api/agents` — create agent
- `GET /api/agents/{id}` — get agent config
- `GET /api/agents/by-slug/{slug}` — get builtin agent by slug
- `PATCH /api/agents/{id}` — update agent config/meta
- `DELETE /api/agents/{id}` — delete agent (cascade: KB links, files, documents)
- `POST /api/agents/{id}/duplicate` — duplicate agent
- `GET /api/agent-groups` — list groups
- `POST /api/agent-groups` — create group

**Migration work:**

1. ✅ `.rest.ts` + `resolved.ts` exist
2. ✅ Stores import from resolved
3. ⬜ E2E tests

**E2E Tests Required:**

```gherkin
@rest @agent @P0
Feature: Agent CRUD via REST
  Scenario: Create a new agent with title and system role
  Scenario: Rename agent via context menu
  Scenario: Delete agent via context menu — confirms and removes
  Scenario: Duplicate agent — creates copy with "(copy)" suffix
  Scenario: Pin/unpin agent — pin icon toggles
  Scenario: Agent config persists after page reload
  Scenario: Builtin inbox agent loads correctly
  Scenario: Move agent to a group
  Scenario: Create agent group
```

---

### F5: Session CRUD

**Depends on:** F4
**Python routers:** `sessions.py`, `session_groups.py`
**Frontend services:** `session/index.rest.ts`, `session/resolved.ts`
**Stores:** `store/session/` (via resolved imports)

**Key endpoints:**

- `POST /api/sessions` — create session (linked to agent)
- `GET /api/sessions` — list sessions
- `DELETE /api/sessions/{id}` — delete session
- `POST /api/session-groups` — create group

**E2E Tests Required:**

```gherkin
@rest @session @P0
Feature: Session Management via REST
  Scenario: Starting a chat creates a new session
  Scenario: Session list shows recent conversations
  Scenario: Delete session removes it from list
  Scenario: Sessions are grouped by agent
```

---

### F6: Topic CRUD

**Depends on:** F5
**Python routers:** `topics.py`
**Frontend services:** `topic/index.rest.ts`, `topic/resolved.ts`
**Stores:** `store/topic/` (via resolved imports)

**Key endpoints:**

- `POST /api/topics` — create topic
- `GET /api/topics` — list topics (by session)
- `PATCH /api/topics/{id}` — update topic title/favorite
- `DELETE /api/topics/{id}` — delete topic

**E2E Tests Required:**

```gherkin
@rest @topic @P0
Feature: Topic Management via REST
  Scenario: Sending a message auto-creates a topic
  Scenario: Topic list shows all conversation topics
  Scenario: Rename topic via context menu
  Scenario: Favorite a topic — moves to favorites section
  Scenario: Delete topic — removes messages and topic
```

---

### F7: Message CRUD

**Depends on:** F5, F6
**Python routers:** `messages.py`
**Frontend services:** `message/index.rest.ts`, `message/resolved.ts`
**Stores:** `store/message/` (via resolved imports)

**Key endpoints:**

- `POST /api/messages` — create message
- `GET /api/messages` — list messages (by topic/session, with pagination)
- `PATCH /api/messages/{id}` — update message content/metadata
- `DELETE /api/messages/{id}` — delete message
- `DELETE /api/messages/batch` — batch delete
- `GET /api/messages/count` — message count

**E2E Tests Required:**

```gherkin
@rest @message @P0
Feature: Message Operations via REST
  Scenario: Messages load correctly when opening a topic
  Scenario: Delete a single message
  Scenario: Edit a message — content updates
  Scenario: Messages paginate correctly for long conversations
  Scenario: Copy message content to clipboard
```

---

### F8: Chat Runtime (AI Chat + Agent Execution)

**Depends on:** F4, F5, F6, F7
**Python routers:** `ai_chat.py`, `ai_agent.py`, `agent_stream.py`, `chat.py`, `follow_up.py`
**Frontend services:** `aiChat.rest.ts`, `aiAgent.rest.ts`, `agentRuntime/index.rest.ts`
**Stores:** `store/chat/slices/aiChat/`, `store/chat/slices/aiAgent/`
**Direct lambdaClient:**

- `store/chat/slices/aiAgent/actions/agentGroup.ts` — `lambdaClient.aiAgent.execGroupAgent.mutate()`
- `src/services/chat/mecha/contextEngineering.ts` — 3 direct calls

**Key endpoints:**

- `POST /api/ai-chat/stream` — streaming chat completion (SSE)
- `POST /api/ai-agent/exec` — execute agent
- `POST /api/ai-agent/exec-group` — execute group agent
- `POST /api/follow-up` — generate follow-up suggestions

**Migration work:**

1. ✅ `.rest.ts` + `resolved.ts` exist
2. ⬜ Migrate `agentGroup.ts` direct lambdaClient call
3. ⬜ Migrate `contextEngineering.ts` direct lambdaClient calls
4. ⬜ E2E tests (critical — this is the core feature)

**E2E Tests Required:**

```gherkin
@rest @chat @P0
Feature: Chat Runtime via REST
  Scenario: Send a message and receive streamed AI response
  Scenario: Stop generation mid-stream
  Scenario: Regenerate last assistant message
  Scenario: Follow-up suggestions appear after response
  Scenario: Chat works with non-default model provider
  Scenario: Error message shown when API key is missing
```

---

### F9: Briefs

**Depends on:** F4
**Python routers:** `briefs.py`
**Frontend services:** `brief.rest.ts`, `brief.resolved.ts`
**Stores:** `store/brief/slices/list/action.ts` (uses resolved)

**E2E Tests Required:**

```gherkin
@rest @brief @P1
Feature: Briefs via REST
  Scenario: Briefs list loads on dashboard
  Scenario: Mark brief as read
  Scenario: Resolve a brief
  Scenario: Delete a brief
```

---

### F10: Notifications

**Depends on:** F1
**Python routers:** `notifications.py`
**Frontend services:** `notification.rest.ts`, `notification.resolved.ts`

**E2E Tests Required:**

```gherkin
@rest @notification @P1
Feature: Notifications via REST
  Scenario: Notification badge shows unread count
  Scenario: Mark notification as read — badge updates
```

---

### F11: Agent Documents + Knowledge Bases

**Depends on:** F4, F12
**Python routers:** `agent_documents.py`, `agent_documents_rest.py`, `agent_document_vfs.py`, `knowledge.py`, `documents.py`
**Frontend services:** `agentDocument.rest.ts`, `knowledgeBase.rest.ts`, `document/index.rest.ts`
**Stores:** `store/agent/slices/knowledge/action.ts` (uses resolved)

**E2E Tests Required:**

```gherkin
@rest @knowledge @P1
Feature: Knowledge Base via REST
  Scenario: Create a knowledge base
  Scenario: Link knowledge base to agent
  Scenario: Upload a document to knowledge base
  Scenario: Document appears in agent's knowledge list
  Scenario: Unlink knowledge base from agent
  Scenario: VFS: list files in agent document tree
  Scenario: VFS: rename a document
```

---

### F12: File Upload + Management

**Depends on:** F1
**Python routers:** `files.py`, `upload.py`
**Frontend services:** `file/index.rest.ts`, `upload.rest.ts`
**Stores:** `store/file/` (uses resolved)
**Direct lambdaClient:** `store/file/slices/fileManager/action.test.ts` (test only)

**E2E Tests Required:**

```gherkin
@rest @file @P1
Feature: File Upload via REST
  Scenario: Upload an image file — preview appears
  Scenario: Upload a document file — listed in files
  Scenario: Delete a file
  Scenario: Presigned URL generation works for S3 uploads
```

---

### F13: RAG + Chunks

**Depends on:** F11
**Python routers:** `chunks.py`
**Frontend services:** `rag.rest.ts`, `rag.resolved.ts`

**E2E Tests Required:**

```gherkin
@rest @rag @P2
Feature: RAG Chunks via REST
  Scenario: Document is chunked after upload
  Scenario: Semantic search returns relevant chunks
```

---

### F14: Agent Eval + Benchmarks

**Depends on:** F4, F11
**Python routers:** `agent_eval.py`, `agent_eval_external.py`
**Frontend services:** `agentEval.rest.ts`, `agentEval.resolved.ts`, `ragEval.rest.ts`
**Stores:** `store/library/slices/ragEval/`

**E2E Tests Required:**

```gherkin
@rest @eval @P2
Feature: Agent Eval via REST
  Scenario: Create an eval benchmark for an agent
  Scenario: Add test cases to benchmark
  Scenario: Run evaluation — results display
```

---

### F15: Tasks

**Depends on:** F4
**Python routers:** `tasks.py`
**Frontend services:** `task.rest.ts`, `task.resolved.ts`
**Stores:** `store/task/` (all slices use resolved)

**E2E Tests Required:**

```gherkin
@rest @task @P1
Feature: Tasks via REST
  Scenario: Create a task
  Scenario: Update task status (pending → in_progress → done)
  Scenario: Delete a task
  Scenario: Task list loads with filters
  Scenario: Add comment to task
```

---

### F16: Tools + Plugins + Skills

**Depends on:** F4
**Python routers:** `plugins.py`, `tools.py`, `skills.py`
**Frontend services:** `plugin/index.rest.ts`, `tool.rest.ts`, `skill/index.rest.ts`
**Stores:** `store/tool/slices/customPlugin/action.ts`, `store/tool/slices/builtin/`
**Direct lambdaClient:**

- `store/tool/slices/builtin/executors/lobe-message.ts` — 4 calls (agentBotProvider.list, botMessage)
- `store/tool/slices/builtin/executors/lobe-topic-reference.ts` — 1 call
- `features/SkillStore/SkillList/UploadSkillModal.tsx` — 1 call

**E2E Tests Required:**

```gherkin
@rest @tools @P1
Feature: Tools and Plugins via REST
  Scenario: Plugin list loads on tools page
  Scenario: Enable/disable a plugin
  Scenario: Skill list loads correctly
  Scenario: Upload a custom skill
```

---

### F17: User Memory

**Depends on:** F1
**Python routers:** `user_memory.py`, `memory.py`
**Frontend services:** `userMemory/index.rest.ts`, `userMemory/crud.rest.ts`, `userMemory/extraction.rest.ts`
**Stores:** Multiple resolved imports

**E2E Tests Required:**

```gherkin
@rest @memory @P1
Feature: User Memory via REST
  Scenario: Memory page loads user memories
  Scenario: Add a memory entry manually
  Scenario: Delete a memory entry
  Scenario: Memory persona loads in chat context
```

---

### F18: AI Infra (Models + Providers)

**Depends on:** F1
**Python routers:** `ai_infra.py`
**Frontend services:** `aiModel/index.rest.ts`, `aiProvider/index.rest.ts`
**Stores:** `store/aiInfra/` (via resolved imports)

**E2E Tests Required:**

```gherkin
@rest @ai-infra @P1
Feature: AI Model & Provider Config via REST
  Scenario: Provider list loads on settings page
  Scenario: Enable/disable a provider
  Scenario: Add custom model to provider
  Scenario: Model selector shows enabled models
  Scenario: Runtime state reflects enabled providers
```

---

### F19: Discover (Market)

**Depends on:** F4
**Python routers:** `market.py`, `market_discover.py`
**Frontend services:** `discover.rest.ts`, `marketApi.rest.ts`
**Stores:** `store/discover/` (multiple slices, all use resolved)

**E2E Tests Required:**

```gherkin
@rest @discover @P2
Feature: Discover Market via REST
  Scenario: Discover page loads featured agents
  Scenario: Search agents by keyword
  Scenario: Install agent from market
  Scenario: View agent detail page
```

---

### F20: Social + Share

**Depends on:** F6
**Python routers:** `social.py`, `share.py`
**Frontend services:** `social.rest.ts`

**E2E Tests Required:**

```gherkin
@rest @social @P2
Feature: Share & Social via REST
  Scenario: Share a conversation topic — generates share link
  Scenario: View shared conversation (public URL)
```

---

### F21: Admin

**Depends on:** F1
**Python routers:** `admin.py`
**Frontend features:** `features/Admin/AdminViewContext.tsx`, `features/Admin/UserSettingsDrawer.tsx`
**Direct lambdaClient:** 4 calls (getUserState, getUserStats)

**E2E Tests Required:**

```gherkin
@rest @admin @P2
Feature: Admin Panel via REST
  Scenario: Admin user list loads
  Scenario: View user settings (read-only)
  Scenario: User stats display correctly
```

---

### F22: Bot Message

**Depends on:** F8
**Python routers:** `bot_message.py`
**Direct lambdaClient:** `store/tool/slices/builtin/executors/lobe-message.ts` (via `lambdaClient.botMessage`)

**E2E Tests Required:**

```gherkin
@rest @bot @P2
Feature: Bot Message via REST
  Scenario: Send message to connected bot platform
  Scenario: Receive bot platform callback
```

---

### F23: Klavis MCP

**Depends on:** F16
**Python routers:** `klavis.py`, `mcp.py`
**Frontend services:** `mcp.rest.ts`
**Direct lambdaClient:** `store/tool/slices/klavisStore/action.ts` — **8 calls** (largest remaining block)

**Migration work:**

1. ⬜ Create `klavis.rest.ts` + `klavis.resolved.ts`
2. ⬜ Migrate 8 direct lambdaClient calls in klavisStore
3. ⬜ E2E tests

**E2E Tests Required:**

```gherkin
@rest @mcp @P2
Feature: Klavis MCP via REST
  Scenario: List MCP server instances
  Scenario: Create MCP server instance
  Scenario: Authenticate MCP server
  Scenario: Delete MCP server instance
```

---

### F24: Cron Jobs

**Depends on:** F4
**Python routers:** `agent_cron_jobs.py`
**Frontend services:** `agentCronJob.rest.ts`, `agentCronJob.resolved.ts`
**Stores:** `store/agent/slices/cron/action.ts`
**Direct lambdaClient:** `store/agent/slices/cron/action.ts` — 2 calls, `hooks/useFetchCronTopics.ts` — 1 call, `routes/(main)/agent/cron/[cronId]/index.tsx` — 1 call

**E2E Tests Required:**

```gherkin
@rest @cron @P2
Feature: Agent Cron Jobs via REST
  Scenario: Create a cron job for an agent
  Scenario: Cron job list loads on agent settings
  Scenario: Delete a cron job
  Scenario: Cron job execution history shows
```

---

### F25: Import / Export

**Depends on:** F4, F7
**Python routers:** `importer.py`, `exporter.py`
**Frontend services:** `import/index.rest.ts`, `export/index.rest.ts`

**E2E Tests Required:**

```gherkin
@rest @import-export @P2
Feature: Import/Export via REST
  Scenario: Export conversations as JSON
  Scenario: Import conversations from JSON file
```

---

### F26: Notebook

**Depends on:** F7
**Python routers:** `notebook.py`
**Frontend services:** `notebook.rest.ts`, `notebook.resolved.ts`
**Stores:** `store/notebook/action.ts` (uses resolved)

**E2E Tests Required:**

```gherkin
@rest @notebook @P2
Feature: Notebook via REST
  Scenario: Create a notebook page
  Scenario: Edit notebook content
  Scenario: Delete notebook page
  Scenario: Notebook list loads correctly
```

---

### F27: Generations (Image + Video)

**Depends on:** F4
**Python routers:** `generation.py`, `generation_batches.py`, `generation_topics.py`, `generations.py`, `image_generation.py`, `video_generation.py`
**Frontend services:** `generation.rest.ts`, `generationBatch.rest.ts`, `generationTopic.rest.ts`, `image.rest.ts`, `video.rest.ts`

**E2E Tests Required:**

```gherkin
@rest @generation @P2
Feature: Generations via REST
  Scenario: Generate an image — result displays
  Scenario: Generation history loads
  Scenario: Delete a generation
```

---

### F28: Settings — API Keys + Creds

**Depends on:** F1
**Python routers:** `api_keys.py`
**Direct lambdaClient:** `routes/(main)/settings/apikey/features/ApiKey.tsx` — 4 calls, `routes/(main)/settings/creds/` — 7 calls across 5 files

**Migration work:**

1. ⬜ Create `apiKey.rest.ts` + `apiKey.resolved.ts` (or use existing creds pattern)
2. ⬜ Migrate 11 direct lambdaClient calls in settings routes
3. ⬜ E2E tests

**E2E Tests Required:**

```gherkin
@rest @settings @P1
Feature: API Keys & Credentials via REST
  Scenario: API key settings page loads
  Scenario: Add an API key for a provider
  Scenario: Delete an API key
  Scenario: Create a credential (KV type)
  Scenario: Edit a credential
```

---

### F29: Agent Signal

**Depends on:** F4
**Python routers:** `agent_signal.py`
**Frontend services:** `agentSignal.rest.ts`, `agentSignal.resolved.ts`

**E2E Tests Required:**

```gherkin
@rest @signal @P2
Feature: Agent Signal via REST
  Scenario: Create a signal policy
  Scenario: Emit a signal — agent reacts
```

---

### F30: Agent Bot Providers

**Depends on:** F4
**Python routers:** `agent_bot_providers.py`
**Frontend services:** `agentBotProvider.rest.ts`, `agentBotProvider.resolved.ts`

**E2E Tests Required:**

```gherkin
@rest @bot-provider @P2
Feature: Agent Bot Providers via REST
  Scenario: List bot providers
  Scenario: Create a bot provider (Discord/Slack/etc)
  Scenario: Delete a bot provider
```

---

## Migration Order (Recommended)

### Wave 1 — Foundation (Unblocks everything)

| #   | Feature       | Priority | Deps  | Direct lambdaClient remaining |
| --- | ------------- | -------- | ----- | ----------------------------- |
| F0  | Auth + Config | P0       | —     | 0                             |
| F1  | User State    | P0       | F0    | 5 (MarketAuthProvider)        |
| F2  | Home + Nav    | P0       | F0,F1 | 0                             |
| F3  | Global Config | P0       | F0    | 0                             |

### Wave 2 — Core CRUD (Enables chat)

| #   | Feature      | Priority | Deps  | Direct lambdaClient remaining |
| --- | ------------ | -------- | ----- | ----------------------------- |
| F4  | Agent CRUD   | P0       | F1,F2 | 0                             |
| F5  | Session CRUD | P0       | F4    | 0                             |
| F6  | Topic CRUD   | P0       | F5    | 0                             |
| F7  | Message CRUD | P0       | F5,F6 | 0                             |

### Wave 3 — Chat Runtime (Core experience)

| #   | Feature      | Priority | Deps  | Direct lambdaClient remaining |
| --- | ------------ | -------- | ----- | ----------------------------- |
| F8  | Chat Runtime | P0       | F4-F7 | 4 (agentGroup, contextEng)    |

### Wave 4 — Supporting Features

| #   | Feature       | Priority | Deps | Direct lambdaClient remaining |
| --- | ------------- | -------- | ---- | ----------------------------- |
| F9  | Briefs        | P1       | F4   | 0                             |
| F10 | Notifications | P1       | F1   | 0                             |
| F12 | File Upload   | P1       | F1   | 0 (test only)                 |
| F15 | Tasks         | P1       | F4   | 0                             |
| F17 | User Memory   | P1       | F1   | 0                             |
| F18 | AI Infra      | P1       | F1   | 0                             |
| F28 | Settings/Keys | P1       | F1   | 11                            |

### Wave 5 — Agent Ecosystem

| #   | Feature       | Priority | Deps   | Direct lambdaClient remaining |
| --- | ------------- | -------- | ------ | ----------------------------- |
| F11 | Agent Docs/KB | P1       | F4,F12 | 0                             |
| F16 | Tools/Plugins | P1       | F4     | 6                             |
| F24 | Cron Jobs     | P2       | F4     | 4                             |
| F29 | Agent Signal  | P2       | F4     | 0                             |
| F30 | Bot Providers | P2       | F4     | 0                             |

### Wave 6 — Advanced + Market

| #   | Feature       | Priority | Deps   | Direct lambdaClient remaining |
| --- | ------------- | -------- | ------ | ----------------------------- |
| F13 | RAG Chunks    | P2       | F11    | 0                             |
| F14 | Eval Bench    | P2       | F4,F11 | 0                             |
| F19 | Discover      | P2       | F4     | 0                             |
| F20 | Social/Share  | P2       | F6     | 0                             |
| F21 | Admin         | P2       | F1     | 4                             |
| F22 | Bot Message   | P2       | F8     | 4                             |
| F23 | Klavis MCP    | P2       | F16    | 8                             |
| F25 | Import/Export | P2       | F4,F7  | 0                             |
| F26 | Notebook      | P2       | F7     | 0                             |
| F27 | Generations   | P2       | F4     | 0                             |

---

## Direct lambdaClient Calls — Full Inventory

These must be migrated to use resolved services:

| File                                                          | Calls    | Domain         |
| ------------------------------------------------------------- | -------- | -------------- |
| `store/tool/slices/klavisStore/action.ts`                     | 8        | F23 Klavis     |
| `layout/AuthProvider/MarketAuth/MarketAuthProvider.tsx`       | 5        | F1 User/Social |
| `layout/AuthProvider/MarketAuth/ProfileSetupModal.tsx`        | 2        | F1 User/Social |
| `layout/AuthProvider/MarketAuth/ClaimResourcesModal.tsx`      | 1        | F1 User/Social |
| `layout/AuthProvider/MarketAuth/useMarketUserProfile.ts`      | 1        | F1 User/Social |
| `layout/AuthProvider/MarketAuth/useSocialConnect.ts`          | 1        | F1 User/Social |
| `store/tool/slices/builtin/executors/lobe-message.ts`         | 4        | F22 Bot        |
| `routes/(main)/settings/apikey/features/ApiKey.tsx`           | 4        | F28 Settings   |
| `features/Admin/AdminViewContext.tsx`                         | 2        | F21 Admin      |
| `features/Admin/UserSettingsDrawer.tsx`                       | 2        | F21 Admin      |
| `routes/(main)/settings/creds/` (5 files)                     | 7        | F28 Settings   |
| `routes/(main)/agent/profile/.../useMarketPublish.ts`         | 2        | F20 Social     |
| `routes/(main)/group/profile/.../useMarketGroupPublish.ts`    | 2        | F20 Social     |
| `store/agent/slices/cron/action.ts`                           | 2        | F24 Cron       |
| `store/chat/slices/aiAgent/actions/agentGroup.ts`             | 1        | F8 Chat        |
| `services/chat/mecha/contextEngineering.ts`                   | 3        | F8 Chat        |
| `store/tool/slices/builtin/executors/lobe-topic-reference.ts` | 1        | F16 Tools      |
| `features/SkillStore/SkillList/UploadSkillModal.tsx`          | 1        | F16 Tools      |
| `features/CommandMenu/useCommandMenu.ts`                      | 1        | F2 Home        |
| `features/PageExplorer/PageExplorerPlaceholder.tsx`           | 1        | F26 Notebook   |
| `hooks/useFetchCronTopics.ts`                                 | 1        | F24 Cron       |
| `routes/(main)/agent/cron/[cronId]/index.tsx`                 | 1        | F24 Cron       |
| **Total**                                                     | **\~53** |                |

---

## Per-Feature Migration Checklist

For each feature `FN`:

- [ ] Verify Python backend router exists and endpoints match TRPC procedures
- [ ] Verify `.rest.ts` service file exists and covers all methods
- [ ] Verify `.resolved.ts` file exists
- [ ] Verify all store imports use `.resolved` (not direct TRPC service)
- [ ] Migrate any direct `lambdaClient` calls in stores/features/routes → resolved service
- [ ] Write E2E feature file (`e2e/src/features/rest/<feature>.feature`)
- [ ] Write E2E step definitions (`e2e/src/steps/rest/<feature>.steps.ts`)
- [ ] Run E2E tests with `NEXT_PUBLIC_USE_REST_API=1`
- [ ] Verify no console errors in browser during E2E run
- [ ] Verify no 500/404 errors in Python backend logs during E2E run
- [ ] Mark feature as ✅ in this skill doc

---

## E2E Test Infrastructure

### Setup

E2E tests use **Cucumber + Playwright** (`e2e/` directory).

```bash
cd e2e
npx cucumber-js --tags "@rest and @P0" # Run P0 REST tests only
```

### Test Environment

```bash
# Terminal 1: Python backend
cd python-backend && .venv/bin/uvicorn main:app --reload --port 8000

# Terminal 2: SPA frontend (REST mode)
PORT=8000 NEXT_PUBLIC_USE_REST_API=1 bun run dev:spa

# Terminal 3: E2E tests
cd e2e && npx cucumber-js --tags "@rest"
```

### Writing a REST E2E Test

1. Create feature file: `e2e/src/features/rest/<domain>.feature`
2. Tag with `@rest` + `@<domain>` + priority (`@P0`/`@P1`/`@P2`)
3. Steps should use Playwright to interact with the actual UI
4. No mocking — tests hit the real Python backend
5. Use `Background` step for auth: `Given 用户已登录系统`
