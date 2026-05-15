# Python Backend — TS Parity Gap Analysis

Status tracker for features present in the TypeScript backend but missing from the Python backend.

## Tier 1 — Core Platform Features

| #   | Feature                                              | TS Source                                                    | Size    | Status                                                      |
| --- | ---------------------------------------------------- | ------------------------------------------------------------ | ------- | ----------------------------------------------------------- |
| 1   | AI Agent Service (full orchestration)                | `aiAgent/index.ts`                                           | 85KB    | ✅ **DONE** — service, types, ingestion, router             |
| 2   | Task System (background jobs, scheduling, lifecycle) | `task.ts`, `taskRunner/`, `taskLifecycle/`, `taskScheduler/` | \~80KB  | ✅ **DONE** — service, runner, scheduler, lifecycle, router |
| 3   | Bot Platform (Discord, Slack, Telegram, etc.)        | `bot/` (92 items)                                            | \~200KB | **SKIPPED** — out of scope                                  |
| 4   | Agent Signal System (event-driven orchestration)     | `agentSignal/` (104 items)                                   | \~100KB | ✅ **DONE** — types, orchestrator, policy engine            |
| 5   | Agent Eval / RAG Eval                                | `agentEval*.ts`, `ragEval.ts`, `agentEvalRun/`               | \~70KB  | ✅ **DONE** — service, benchmarks, datasets, runs, router   |

## Tier 2 — Important Capabilities

| #   | Feature                                       | TS Source                                   | Python Status                                     |
| --- | --------------------------------------------- | ------------------------------------------- | ------------------------------------------------- |
| 6   | Image Generation + ComfyUI                    | `image/`, `comfyui/` (68 items)             | Partial — DALL-E only                             |
| 7   | Video Generation                              | `video/`, `generation/video.ts`             | **TODO**                                          |
| 8   | Search Provider Abstraction (12 backends)     | `search/` (33 items)                        | ✅ **DONE** — 12 providers, service, router, tool |
| 9   | Agent Document VFS                            | `agentDocumentVfs/` (39KB)                  | **TODO**                                          |
| 10  | Generation Service (titles, summaries, batch) | `generation/index.ts`, `generationBatch.ts` | Partial — basic router exists                     |
| 11  | Onboarding Service                            | `onboarding/` (27KB)                        | **TODO**                                          |
| 12  | Queue Service                                 | `queue/`                                    | ✅ **DONE** — abstract + in-memory backend        |

## Tier 3 — Supporting Features

| #   | Feature                                | TS Source                              | Status   |
| --- | -------------------------------------- | -------------------------------------- | -------- |
| 13  | OAuth Device Flow                      | `oauthDeviceFlow/`                     | **TODO** |
| 14  | Klavis Integration                     | `klavis.ts`                            | **TODO** |
| 15  | Agent Cron Jobs                        | `agentCronJob.ts`                      | **TODO** |
| 16  | Agent Notifications                    | `agentNotify.ts`                       | **TODO** |
| 17  | Brief Service                          | `brief/`                               | **TODO** |
| 18  | Email Service                          | `email/`                               | **TODO** |
| 19  | Risk Control                           | `riskControl/`                         | **TODO** |
| 20  | Error Classification                   | `toolExecution/errorClassification.ts` | **TODO** |
| 21  | GTD Tool                               | `serverRuntimes/gtd.ts`                | **TODO** |
| 22  | Cron Tool                              | `serverRuntimes/cron.ts`               | **TODO** |
| 23  | Creds Tool                             | `serverRuntimes/creds.ts`              | **TODO** |
| 24  | Cloud Sandbox                          | `serverRuntimes/cloudSandbox.ts`       | **TODO** |
| 25  | Lobe Agent Tool (sub-agent delegation) | `serverRuntimes/lobeAgent.ts`          | **TODO** |
| 26  | Subscription / Billing                 | `subscription`, `spend`, `topUp`       | **TODO** |
| 27  | Account Deletion                       | `accountDeletion`                      | **TODO** |
| 28  | Skill Maintainer                       | `skillMaintainer/`                     | **TODO** |
| 29  | Agent Tracing                          | `AgentTracing/`                        | **TODO** |
| 30  | Async Workflows (QStash)               | `workflows-hono/`                      | **TODO** |

## Current Sprint

### Platform Layer

- [x] Gap analysis document created
- [x] Task System — service, runner, scheduler, lifecycle, router (`app/services/task/`, `app/routers/tasks.py`)
- [x] Agent Signal — types, policy engine, orchestrator (`app/services/agent_signal/`)
- [x] Agent Eval — service, benchmarks, datasets, runs, router (`app/services/agent_eval/`, `app/routers/agent_eval.py`)
- [x] Queue Service — abstract interface + in-memory backend (`app/services/queue/`)

### Search Provider Abstraction ✅ COMPLETE

- [x] Abstract search provider interface (`app/services/search/providers/base.py`)
- [x] Tavily, Brave, Google, Exa, SearXNG, Jina implementations
- [x] Firecrawl, Kagi, Bocha, Search1API, Anspire, Serper implementations
- [x] Provider registry + factory (`app/services/search/providers/registry.py`)
- [x] SearchService orchestrator with fallback chain (`app/services/search/service.py`)
- [x] 12 provider API key env vars added to config
- [x] web_search tool refactored to use SearchService
- [x] Web search HTTP router (`app/routers/web_search.py`)
- [ ] Tests (next sprint)

### AI Agent Service ✅ COMPLETE

- [x] Type definitions — `AgentError`, `AgentErrorType`, `ExecAgentParams/Result`, `ExecGroupAgentParams/Result`, `ExecSubAgentTaskParams/Result`, `AppContext`, `ResumeApproval`, `ToolManifest`, `StepEvent` (`app/services/ai_agent/types.py`)
- [x] Attachment ingestion — download external files, upload to S3, classify image/video/doc, create DB records (`app/services/ai_agent/ingest_attachment.py`)
- [x] Core `AiAgentService` class (`app/services/ai_agent/service.py`):
  - [x] Agent resolution by ID or slug from DB
  - [x] Topic auto-creation with metadata (cronJobId, taskId, bot context)
  - [x] Topic metadata tracking (runningOperation for reconnect)
  - [x] User message + assistant placeholder DB persistence
  - [x] File ingestion: external files + existing file ID resolution
  - [x] Tool discovery from AgentSkill DB + builtin tools + client function tools
  - [x] User persona/memory fetch and injection
  - [x] History message loading from topic or explicit IDs
  - [x] Human approval DB persistence (approved/rejected/rejected_continue)
  - [x] Agent signal integration (fire agent.user.message events)
  - [x] Structured error types — typed errors, assistant message error updates
  - [x] `exec_agent()` — full orchestration entry point
  - [x] `exec_group_agent()` — Group Agent (Supervisor) with topic groupId
  - [x] `exec_sub_agent_task()` — SubAgent with Thread isolation
  - [x] `interrupt_task()` — interrupt by threadId or operationId
- [x] HTTP router with 5 endpoints (`app/routers/ai_agent.py`):
  - POST `/api/ai-agent/exec` — execute agent
  - POST `/api/ai-agent/exec/stream` — execute agent with SSE streaming
  - POST `/api/ai-agent/exec-group` — execute group agent
  - POST `/api/ai-agent/exec-sub-agent` — execute sub-agent task
  - POST `/api/ai-agent/interrupt` — interrupt task
- [x] Wired into `main.py`
- [x] All files pass `py_compile` syntax check

## Completed Previously

- Core chat loop (chat, RAG, memory, tools, MCP, agent runtime, skills)
- Performance fixes (16/16 applied)
- Production safety fixes (SSRF, sandbox, rate limiting)
- Database models + Alembic migrations (75 tables)

---

## Remaining Gaps: TS → Python Backend

### 1. Services — TS directories with no Python equivalent

| TS Service Dir                       | Description                                                                         | Priority | Notes                                                                     |
| ------------------------------------ | ----------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------- |
| `agentDocumentVfs/`                  | Virtual filesystem for agent documents (read/write/list)                            | High     | Powers inline document editing in agents                                  |
| `agentRuntime/` (77KB)               | Full step-level runner with hooks, skill resolver, tool executor                    | High     | ✅ Hooks, abort, cost, compression, fallback, error classification DONE   |
| `generation/` + `generationBatch.ts` | Title/summary generation, batch processing                                          | Medium   | Python has basic `generation.py` router — missing batch, video generation |
| `brief/`                             | Brief synthesis from conversation history                                           | Medium   | Python has `briefs` model but no synthesis service                        |
| `toolExecution/` (orchestrator)      | Tool execution dispatcher with error classification, device proxy, builtin dispatch | High     | ✅ Error classification DONE — still missing device proxy                 |
| `aiChat/`                            | Chat completions with structured SSE events (text, reasoning, tool_calls, usage)    | Medium   | Python `chat_service.py` streams tokens — lacks structured event types    |
| `skillMaintainer/`                   | Auto-update skill manifests from market                                             | Low      |                                                                           |
| `systemAgent/`                       | System agent for auto-titles, translation, tag generation                           | Medium   | Python has some generation endpoints, not the full system agent           |
| `discover/`                          | Agent/plugin marketplace discovery service                                          | Low      | Python `market.py` router exists — may need parity check                  |
| `changelog/`                         | Changelog aggregation service                                                       | Low      |                                                                           |
| `gateway/`                           | WebSocket gateway for real-time agent streaming                                     | Medium   | Python uses SSE; WS gateway needed for mobile/desktop reconnect           |
| `onboarding/`                        | User onboarding flow orchestration                                                  | Low      |                                                                           |
| `oauthDeviceFlow/`                   | OAuth 2.0 device authorization flow                                                 | Low      |                                                                           |
| `klavis/`                            | Klavis tool manifest integration                                                    | Low      |                                                                           |
| `email/`                             | Transactional email via Resend/SES                                                  | Low      |                                                                           |
| `riskControl/`                       | Content policy, rate limiting per-model                                             | Medium   | Python has rate limiting but no content policy classification             |
| `sandbox/`                           | Cloud code sandbox (E2B, Daytona)                                                   | Medium   | Python has local `code_interpreter.py` — no cloud sandbox                 |
| `comfyui/`                           | ComfyUI workflow execution for image gen                                            | Low      |                                                                           |
| `webhookUser/`                       | Webhook-triggered user actions                                                      | Low      |                                                                           |
| `doc/`                               | Documentation service                                                               | Low      |                                                                           |
| `taskReview/`                        | Task review / QA after completion                                                   | Low      |                                                                           |
| `taskTemplate/`                      | Reusable task templates                                                             | Low      |                                                                           |

### 2. Tool Execution — TS server runtimes vs Python tools

| TS Runtime (`serverRuntimes/`) | Python Equivalent (`app/tools/`)      | Gap                                             |
| ------------------------------ | ------------------------------------- | ----------------------------------------------- |
| `activator.ts`                 | `activator.py` ✅                     | —                                               |
| `calculator.ts`                | `calculator.py` ✅                    | —                                               |
| `topicReference.ts`            | `topic_reference.py` ✅               | —                                               |
| `skillStore.ts`                | `skill_store.py` ✅                   | —                                               |
| `skills.ts`                    | `skills.py` ✅                        | —                                               |
| `memory.ts`                    | `memory_tool.py` ✅                   | —                                               |
| `notebook.ts`                  | (via `notebook.py` router) ✅         | —                                               |
| `userInteraction.ts`           | `user_interaction.py` ✅              | —                                               |
| `webBrowsing.ts`               | `url_crawler.py` + `web_search.py` ✅ | —                                               |
| `agentDocuments.ts`            | **MISSING**                           | Read/write/list agent document VFS              |
| `agentMarketplace.ts`          | **MISSING**                           | Search/install agents from marketplace          |
| `brief.ts`                     | **MISSING**                           | Generate/list briefs for a topic                |
| `cloudSandbox.ts`              | **MISSING**                           | E2B/Daytona cloud sandbox execution             |
| `creds.ts`                     | **MISSING**                           | OAuth credential store for tools                |
| `cron.ts`                      | **MISSING**                           | CRUD agent cron jobs                            |
| `gtd.ts`                       | **MISSING**                           | GTD (task management) tool                      |
| `localSystem.ts`               | **MISSING**                           | Local desktop file/process access (Electron)    |
| `lobeAgent.ts`                 | **MISSING**                           | Sub-agent delegation tool                       |
| `message/` (dispatcher)        | **MISSING**                           | Cross-platform message send (bot platforms)     |
| `remoteDevice.ts`              | **MISSING**                           | Remote device proxy (desktop → cloud)           |
| `task.ts`                      | **MISSING**                           | Task CRUD from within agent conversation        |
| `webOnboarding.ts`             | **MISSING**                           | Interactive onboarding steps                    |
| `errorClassification.ts`       | `error_classification.py` ✅          | —                                               |
| `deviceProxy.ts`               | **MISSING**                           | Proxy tool calls to Electron desktop client     |
| `builtin.ts` (dispatcher)      | `registry.py` ⚠️ Partial              | TS has richer dispatch with manifest validation |

### 3. Agent Runtime — Feature-level gaps within `agentRuntime/`

| Feature                                                          | TS (`agentRuntime/`, 77KB)                                          | Python (`agent_runtime.py`, 36KB)                  | Gap                              |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------- |
| Hook system (`beforeStep`, `afterStep`, `onComplete`, `onError`) | ✅ Full lifecycle hooks, external dispatch                          | ✅ `HookDispatcher` + webhook delivery             | —                                |
| Skill Resolver                                                   | ✅ Resolves skill manifests → tool definitions per step             | ❌ Tools fixed at operation start                  | Dynamic per-step tool resolution |
| Step-level structured events                                     | ✅ `text`, `reasoning`, `tool_calls`, `usage`, `error`, `grounding` | ✅ `StepPresentationData` with all fields          | —                                |
| Context compression (compactor)                                  | ✅ Auto-compress long contexts mid-conversation                     | ✅ `context_compressor.py`                         | —                                |
| Cost tracking                                                    | ✅ Per-step and total cost accumulation                             | ✅ Per-step + cumulative cost in `llm_node`        | —                                |
| Abort signal propagation                                         | ✅ `AbortSignal` checked between every stage                        | ✅ `AbortSignal` + cooperative checks in all nodes | —                                |
| Multi-model fallback                                             | ✅ Retry with fallback model on provider error                      | ✅ `model_fallback.py` with configurable chains    | —                                |
| Content policy enforcement                                       | ✅ Detect + handle policy violations                                | ✅ `content_policy.py` — pre/post LLM + provider   | —                                |

### 4. Data Layer — Models that exist but lack service logic

| Model                             | Python Model File   | Service/Router              | Gap                                    |
| --------------------------------- | ------------------- | --------------------------- | -------------------------------------- |
| `AgentCronJob`                    | `agent_ops.py` ✅   | ❌ No service               | Need CRUD + scheduler integration      |
| `AgentDocument`                   | `agent_ops.py` ✅   | ❌ No VFS service           | Need read/write/list + VFS abstraction |
| `AgentBotProvider`                | `agent_ops.py` ✅   | ❌ No service               | Bot platform — out of scope            |
| `UserPersonaDocumentHistory`      | `persona.py` ✅     | ❌ No versioning service    | Need persona diff/snapshot logic       |
| `MessageGroup`                    | `message_ext.py` ✅ | ❌ No service               | Need group message CRUD                |
| `MessageTts` / `MessageTranslate` | `message_ext.py` ✅ | ❌ No TTS/translate service | Need TTS generation + translation      |
| `TopicDocument`                   | `topic_ext.py` ✅   | ❌ No service               | Document ↔ topic linking               |
| `TopicShare`                      | `topic_ext.py` ✅   | ⚠️ `share.py` router exists | May need parity check                  |

### 5. Infrastructure Gaps

| Feature                    | TS Implementation                                | Python Status      | Priority                                       |
| -------------------------- | ------------------------------------------------ | ------------------ | ---------------------------------------------- |
| **QStash async workflows** | `workflows-hono/` — durable multi-step workflows | ❌ Not implemented | Medium — use Celery/Dramatiq or simple asyncio |
| **WebSocket gateway**      | `gateway/` — real-time bidirectional streaming   | ❌ SSE only        | Medium — needed for desktop/mobile reconnect   |
| **Agent tracing**          | `AgentTracing/` — step-level execution snapshots | ❌ Langfuse only   | Low — Langfuse covers most tracing needs       |
| **Subscription / billing** | `subscription`, `spend`, `topUp` services        | ❌ Not implemented | Low — depends on business requirements         |
| **Image gen (ComfyUI)**    | `comfyui/` — workflow-based image generation     | ❌ DALL-E only     | Low                                            |
| **Video generation**       | `video/`, `generation/video.ts`                  | ❌ Not implemented | Low                                            |

### 6. Summary — Priority ranking

**High priority (blocks core agent UX):**

1. ~~Agent Runtime hooks system~~ ✅ DONE — `agent_runtime_hooks/`
2. ~~Tool error classification + retry logic~~ ✅ DONE — `error_classification.py`
3. Agent Document VFS service
4. Structured SSE event types in `aiChat` / streaming
5. ~~Context compression (compactor)~~ ✅ DONE — `context_compressor.py`
6. ~~Missing server runtime tools~~ ✅ DONE — `gtd_tool.py`, `task_tool.py`, `brief_tool.py`, `lobe_agent_tool.py`, `agent_documents_tool.py`, `notebook_tool.py`

**High priority (core functionality gaps) — ALL DONE:**

- ~~System Agent Service~~ ✅ DONE — `system_agent.py` (title gen, translation, brief synthesis, task handoff)
- ~~Task Review Service~~ ✅ DONE — `task_review.py` (LLM-based rubric evaluation)
- ~~Task Template Service~~ ✅ DONE — `task_template.py` (daily recommendations, skill eligibility)
- ~~Agent Signal Router~~ ✅ DONE — `routers/agent_signal.py` (emit, policies CRUD, cleanup)
- ~~Brief Service + Router~~ ✅ DONE — `brief.py` + `routers/briefs.py` (CRUD, resolve, dismiss)
- ~~Agent Cron Job Router~~ ✅ DONE — `routers/agent_cron_jobs.py` (full CRUD, batch ops, stats)

**Medium priority (improves robustness):** 7. ~~Content policy enforcement~~ ✅ DONE — `content_policy.py` 8. ~~Multi-model fallback~~ ✅ DONE — `model_fallback.py` 9. ~~Cost tracking per operation~~ ✅ DONE — integrated into `llm_node` 10. Cloud sandbox integration (E2B) 11. Generation batch service 12. WebSocket gateway for real-time streaming 13. Risk control service

**Low priority (nice-to-have / domain-specific):** 14. ComfyUI, video generation 15. ~~Cron jobs service~~ ✅ DONE — `routers/agent_cron_jobs.py` 16. Credential store tool 17. OAuth device flow 18. Email service 19. Skill maintainer 20. Agent tracing (beyond Langfuse) 21. Subscription / billing
