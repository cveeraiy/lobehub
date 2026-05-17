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
| 9   | Agent Document VFS                            | `agentDocumentVfs/` (39KB)                  | ✅ **DONE** — service, types, errors, router      |
| 10  | Generation Service (titles, summaries, batch) | `generation/index.ts`, `generationBatch.ts` | Partial — basic router exists                     |
| 11  | Onboarding Service                            | `onboarding/` (27KB)                        | **TODO**                                          |
| 12  | Queue Service                                 | `queue/`                                    | ✅ **DONE** — abstract + in-memory backend        |

## Tier 3 — Supporting Features

| #   | Feature                                | TS Source                              | Status                                                               |
| --- | -------------------------------------- | -------------------------------------- | -------------------------------------------------------------------- |
| 13  | OAuth Device Flow                      | `oauthDeviceFlow/`                     | **TODO**                                                             |
| 14  | Klavis Integration                     | `klavis.ts`                            | **TODO**                                                             |
| 15  | Agent Cron Jobs                        | `agentCronJob.ts`                      | ✅ **DONE** — `routers/agent_cron_jobs.py` (full CRUD, batch, stats) |
| 16  | Agent Notifications                    | `agentNotify.ts`                       | **TODO**                                                             |
| 17  | Brief Service                          | `brief/`                               | ✅ **DONE** — `brief/service.py` + `routers/briefs.py`               |
| 18  | Email Service                          | `email/`                               | **TODO**                                                             |
| 19  | Risk Control                           | `riskControl/`                         | ✅ **DONE** — `content_policy/` + `tools/_safety.py`                 |
| 20  | Error Classification                   | `toolExecution/errorClassification.ts` | ✅ **DONE** — `error_classification/service.py`                      |
| 21  | GTD Tool                               | `serverRuntimes/gtd.ts`                | ✅ **DONE** — `tools/gtd_tool.py`                                    |
| 22  | Cron Tool                              | `serverRuntimes/cron.ts`               | ✅ **DONE** — `routers/agent_cron_jobs.py` (CRUD from agent context) |
| 23  | Creds Tool                             | `serverRuntimes/creds.ts`              | **TODO**                                                             |
| 24  | Cloud Sandbox                          | `serverRuntimes/cloudSandbox.ts`       | **TODO**                                                             |
| 25  | Lobe Agent Tool (sub-agent delegation) | `serverRuntimes/lobeAgent.ts`          | ✅ **DONE** — `tools/lobe_agent_tool.py`                             |
| 26  | Subscription / Billing                 | `subscription`, `spend`, `topUp`       | **TODO**                                                             |
| 27  | Account Deletion                       | `accountDeletion`                      | **TODO**                                                             |
| 28  | Skill Maintainer                       | `skillMaintainer/`                     | **TODO**                                                             |
| 29  | Agent Tracing                          | `AgentTracing/`                        | **TODO**                                                             |
| 30  | Async Workflows (QStash)               | `workflows-hono/`                      | **TODO**                                                             |

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
- Agent runtime hooks, abort signal, cost tracking, context compression, model fallback, content policy
- System agent, task review, task template, brief service, agent cron jobs
- Agent Document VFS, structured SSE events, GTD/task/brief/lobe-agent tools
- Structural refactoring: all services as packages, agent_runtime split into 7 modules, router auto-registry

---

## REST API Endpoint Gap Analysis (TS TRPC → Python REST)

> Last updated: 2026-05-16. Comprehensive procedure-level comparison of all TS TRPC routers vs Python REST endpoints.

### Fully Covered Routers (no gaps)

| TS Router           | Python Router        | Procedures                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent.ts`          | `agents.py`          | ✅ 20/20 — queryAgents, createAgent, createAgentOnly, duplicateAgent, removeAgent, updateAgentConfig, getAgentConfig, getAgentConfigById, getBuiltinAgent, checkByMarketIdentifier, getAgentByMarketIdentifier, getAgentByForkedFromIdentifier, createAgentFiles, deleteAgentFile, toggleFile, createAgentKnowledgeBase, deleteAgentKnowledgeBase, toggleKnowledgeBase, getKnowledgeBasesAndFiles, updateAgentPinned                                                                                                       |
| `agentGroup.ts`     | `chat_groups.py`     | ✅ 15/15 — createGroup, createGroupWithMembers, getGroups, getGroup, getGroupDetail, updateGroup, deleteGroup, duplicateGroup, getGroupAgents, addAgentsToGroup, batchCreateAgentsInGroup, removeAgentsFromGroup, updateAgentInGroup, checkAgentsBeforeRemoval, getGroupByForkedFromIdentifier                                                                                                                                                                                                                             |
| `session.ts`        | `sessions.py`        | ✅ 13/13 — createSession, batchCreateSessions, getSessions, getGroupedSessions, cloneSession, countSessions, searchSessions, rankSessions, removeSession, removeAllSessions, updateSession, updateSessionConfig, updateSessionChatConfig                                                                                                                                                                                                                                                                                   |
| `sessionGroup.ts`   | `session_groups.py`  | ✅ 6/6 — createSessionGroup, getSessionGroup, removeSessionGroup, removeAllSessionGroups, updateSessionGroup, updateSessionGroupOrder                                                                                                                                                                                                                                                                                                                                                                                      |
| `thread.ts`         | `threads.py`         | ✅ 7/7 — createThread, createThreadWithMessage, getThread, getThreads, removeThread, removeAllThreads, updateThread                                                                                                                                                                                                                                                                                                                                                                                                        |
| `message.ts`        | `messages.py`        | ✅ 28/28 — createMessage, getMessages, listAll, searchMessages, count, countWords, getHeatmaps, rankModels, removeMessage, removeMessages, removeAllMessages, removeMessagesByAssistant, removeMessagesByGroup, removeMessageQuery, update, updateMetadata, updateMessageGroupMetadata, updateMessagePlugin, updatePluginState, updatePluginError, updateToolArguments, updateToolMessage, updateTranslate, updateTTS, updateMessageRAG, addFilesToMessage, createCompressionGroup, cancelCompression, finalizeCompression |
| `topic.ts`          | `topics.py`          | ✅ 24/24 — createTopic, batchCreateTopics, getTopics, getAllTopics, getTopicContext, countTopics, hasTopics, searchTopics, recentTopics, rankTopics, getCronTopicsGroupedByCronJob, cloneTopic, removeTopic, removeAllTopics, batchDelete, batchDeleteByAgentId, batchDeleteBySessionId, updateTopic, updateTopicMetadata, enableSharing, disableSharing, getShareInfo, updateShareVisibility, importTopic                                                                                                                 |
| `document.ts`       | `documents.py`       | ✅ 14/14 — createDocument, createDocuments, queryDocuments, getDocumentById, updateDocument, deleteDocument, deleteDocuments, getFolderBreadcrumb, listDocumentHistory, getDocumentHistoryItem, compareDocumentHistoryItems, saveDocumentHistory, parseDocument, parseFileContent                                                                                                                                                                                                                                          |
| `chunk.ts`          | `chunks.py`          | ✅ 7/7 — createParseFileTask, retryParseFileTask, createEmbeddingChunksTask, getChunksByFileId, getFileContents, semanticSearch, semanticSearchForChat                                                                                                                                                                                                                                                                                                                                                                     |
| `notification.ts`   | `notifications.py`   | ✅ 6/6 — list, archive, archiveAll, markAsRead, markAllAsRead, unreadCount                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `plugin.ts`         | `plugins.py`         | ✅ 6/6 — createPlugin, createOrInstallPlugin, getPlugins, removePlugin, removeAllPlugins, updatePlugin                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `knowledgeBase.ts`  | `knowledge.py`       | ✅ 8/8 — createKnowledgeBase, getKnowledgeBases, getKnowledgeBaseById, updateKnowledgeBase, removeKnowledgeBase, removeAllKnowledgeBases, addFilesToKnowledgeBase, removeFilesFromKnowledgeBase                                                                                                                                                                                                                                                                                                                            |
| `agentSkills.ts`    | `skills.py`          | ✅ 15/15 — create, list, getById, getByName, getByIdentifier, getByIdWithZipUrl, search, update, delete, importFromUrl, importFromGitHub, importFromMarket, importFromZip, listResources, readResource                                                                                                                                                                                                                                                                                                                     |
| `agentCronJob.ts`   | `agent_cron_jobs.py` | ✅ 10/10 — create, list, findByAgent, findById, update, delete, batchUpdateStatus, getStats, getNearDepletion, resetExecutions                                                                                                                                                                                                                                                                                                                                                                                             |
| `home.ts`           | `home.py`            | ✅ 3/3 — getSidebarAgentList, searchAgents, updateAgentSessionGroupId                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `brief.ts`          | `briefs.py`          | ✅ 8/8 — create, list, find, findByTaskId, listUnresolved, markRead, resolve, delete                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `notebook.ts`       | `notebook.py`        | ✅ 5/5 — createDocument, listDocuments, getDocument, updateDocument, deleteDocument                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `userMemory.ts`     | `user_memory.py`     | ✅ 20/20 — deleteAll, getActivities, getContexts, getExperiences, getIdentities, getPreferences, getPersona, createIdentity, deleteActivity, deleteContext, deleteExperience, deleteIdentity, deletePreference, updateActivity, updateContext, updateExperience, updateIdentity, updatePreference, getMemoryExtractionTask, requestMemoryFromChatTopic                                                                                                                                                                     |
| `recent.ts`         | `recent.py`          | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `search.ts`         | `search.py`          | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `share.ts`          | `share.py`           | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `upload.ts`         | `upload.py`          | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `usage.ts`          | `usage.py`           | ✅ 3/3                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `followUpAction.ts` | `follow_up.py`       | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `importer.ts`       | `importer.py`        | ✅ 1/1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `apiKey.ts`         | `api_keys.py`        | ✅ 7/7                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

### Partially Covered Routers

#### `agentDocument.ts` → `agent_documents.py` + `agent_document_vfs.py` — ⚠️ 23/36

Python covers VFS basics (list, stat, read, write, mkdir, rename, copy, delete, trash, restore, empty-trash) + skill-by-path + document-by-ID ops. Missing \~13 advanced procedures:

| Missing TS Procedure       | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `cloneDocuments`           | Clone all documents from one agent to another    |
| `createForTopic`           | Create a document linked to a topic              |
| `getContext`               | Get agent document context for LLM injection     |
| `getDocumentsMap`          | Get a map of all documents keyed by ID           |
| `getTemplates`             | Get available document templates                 |
| `hasDocuments`             | Check if agent has any documents                 |
| `initializeFromTemplate`   | Initialize agent documents from a template       |
| `modifyNodes`              | Modify editor nodes in a document                |
| `replaceDocumentContent`   | Full content replacement                         |
| `upsertDocument`           | Upsert document by path/slug                     |
| `listDocuments` (filtered) | Query-filtered listing with more params          |
| `updateLoadRule`           | Update document load rule (separate from policy) |
| `deleteAllDocuments`       | Delete all documents for an agent                |

#### `task.ts` → `tasks.py` — ⚠️ 13/33

Python has basic CRUD (create, list, find, detail, update, delete, run, status, comments, subtasks, topics, briefs, clearAll, lifecycle). Missing \~20 advanced procedures:

| Missing TS Procedure                                     | Description                            |
| -------------------------------------------------------- | -------------------------------------- |
| `addDependency` / `removeDependency` / `getDependencies` | Task dependency graph                  |
| `getCheckpoint` / `updateCheckpoint`                     | Task checkpoint save/restore           |
| `getReview` / `runReview` / `updateReview`               | Task review system                     |
| `getTaskTree`                                            | Hierarchical task tree                 |
| `groupList`                                              | List tasks grouped by status/priority  |
| `heartbeat` / `watchdog`                                 | Task liveness monitoring               |
| `cancelTopic` / `deleteTopic`                            | Topic management within tasks          |
| `getPinnedDocuments` / `pinDocument` / `unpinDocument`   | Task-pinned documents                  |
| `reorderSubtasks`                                        | Reorder subtasks                       |
| `updateConfig`                                           | Update task config                     |
| `addComment` / `deleteComment` / `updateComment`         | Comment CRUD (partial — create exists) |

#### `ragEval.ts` → `rag_eval.py` — ⚠️ 2/14

Python has only `startEvaluationTask` and `checkEvaluationStatus`. Missing 12 dataset/evaluation CRUD procedures:

| Missing TS Procedure   | Description               |
| ---------------------- | ------------------------- |
| `createDataset`        | Create evaluation dataset |
| `getDatasets`          | List all datasets         |
| `updateDataset`        | Update dataset metadata   |
| `removeDataset`        | Delete dataset            |
| `createDatasetRecords` | Add records to dataset    |
| `getDatasetRecords`    | List dataset records      |
| `updateDatasetRecords` | Update records            |
| `removeDatasetRecords` | Delete records            |
| `importDatasetRecords` | Import records from file  |
| `createEvaluation`     | Create evaluation run     |
| `getEvaluationList`    | List evaluations          |
| `removeEvaluation`     | Delete evaluation         |

#### `agentEval.ts` → `agent_eval.py` — ⚠️ 13/34

Python has benchmarks (create, list), datasets (create, list), runs (create, list, get, execute), test cases (create, batch). Missing \~21 advanced procedures:

| Missing TS Procedure                                               | Description             |
| ------------------------------------------------------------------ | ----------------------- |
| `abortRun`                                                         | Abort an evaluation run |
| `deleteBenchmark` / `getBenchmark` / `updateBenchmark`             | Benchmark management    |
| `deleteDataset` / `getDataset` / `updateDataset` / `importDataset` | Dataset management      |
| `deleteRun` / `updateRun` / `updateRunMetrics` / `updateRunStatus` | Run management          |
| `deleteTestCase` / `getTestCase` / `updateTestCase`                | Test case management    |
| `getResumableCases` / `resumeRunCase` / `batchResumeRunCases`      | Resume support          |
| `retryRunCase` / `retryRunErrors`                                  | Retry support           |
| `getRunProgress` / `getRunResults` / `parseDatasetFile`            | Results & progress      |

#### `file.ts` → `files.py` — ⚠️ 13/16

Python covers most file operations. Missing 3 knowledge-item-specific procedures:

| Missing TS Procedure            | Description                                |
| ------------------------------- | ------------------------------------------ |
| `getKnowledgeItemStatusesByIds` | Get async task statuses for multiple files |
| `resolveKnowledgeItemIds`       | Resolve file IDs from knowledge items      |
| `deleteKnowledgeItemsByQuery`   | Delete knowledge items by query filter     |

#### `user.ts` → `user.py` — ⚠️ 20/22

Nearly complete. Missing 2 minor onboarding procedures:

| Missing TS Procedure     | Description                      |
| ------------------------ | -------------------------------- |
| `readOnboardingDocument` | Read onboarding document content |
| `saveUserQuestion`       | Save user's onboarding question  |

#### `admin.ts` → `admin.py` — ⚠️ Different structure

TS has 5 admin procedures (`getUserState`, `getUserStats`, `getUserSettings`, `updateUserPermissions`, `updateUserSettings`). Python has 6 endpoints with different structure (system stats, user count, user CRUD). Missing:

| Missing TS Procedure    | Description                         |
| ----------------------- | ----------------------------------- |
| `getUserSettings`       | Get specific user's settings object |
| `updateUserPermissions` | Update user permissions             |
| `updateUserSettings`    | Update user settings as admin       |

### Entire TS Routers Missing from Python

| TS Router                | Procedures | Description                                                                                                                                                                                                                                                                               | Priority |
| ------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `userMemories.ts`        | \~20       | ✅ **DONE** — Advanced memory queries, vector search, tool-add endpoints, re-embed, extraction (`app/routers/user_memory.py` + `src/services/userMemory/*.rest.ts`)                                                                                                                       | **P0**   |
| `agentEvalExternal.ts`   | 10         | External evaluation API — not called from SPA, server-internal only                                                                                                                                                                                                                       | P1       |
| ~~`botMessage.ts`~~      | 0          | ~~Bot platform messaging~~ ✅ **DONE** — `bot_message.py` (18 stub endpoints; platform adapters needed)                                                                                                                                                                                   | ~~P2~~   |
| ~~`aiAgent.ts`~~         | 0          | ~~Advanced client/intervention ops~~ ✅ **DONE** — 8 endpoints added to `ai_agent.py` (createOperation, getOperationStatus, processHumanIntervention, refreshGatewayToken, getSubAgentTaskStatus, createClientTaskThread, createClientGroupAgentTaskThread, updateClientTaskThreadStatus) | ~~P2~~   |
| ~~`aiChat.ts`~~          | 0          | ~~`outputJSON`, `sendMessageInServer`~~ ✅ **DONE** — `ai_chat.py`                                                                                                                                                                                                                        | ~~P2~~   |
| `comfyui.ts`             | 3          | ComfyUI image generation — not called from SPA, desktop-only                                                                                                                                                                                                                              | P3       |
| `device.ts`              | 3          | Device management — not called from SPA, desktop-only                                                                                                                                                                                                                                     | P3       |
| ~~`generation.ts`~~      | 0          | ~~`deleteGeneration`, `getGenerationStatus`~~ ✅ **DONE** — `generations.py`                                                                                                                                                                                                              | ~~P3~~   |
| ~~`generationBatch.ts`~~ | 0          | ~~`deleteGenerationBatch`, `getGenerationBatches`~~ ✅ **DONE** — `generation_batches.py`                                                                                                                                                                                                 | ~~P3~~   |
| ~~`generationTopic.ts`~~ | 0          | ~~Generation topic CRUD~~ ✅ **DONE** — `generation_topics.py`                                                                                                                                                                                                                            | ~~P3~~   |
| ~~`klavis.ts`~~          | 0          | ~~Klavis MCP plugin integration~~ ✅ **DONE** — `klavis.py` (7 endpoints)                                                                                                                                                                                                                 | ~~P3~~   |
| `oauthDeviceFlow.ts`     | 4          | OAuth device authorization flow — not called from SPA                                                                                                                                                                                                                                     | P3       |
| `agentNotify.ts`         | 1          | Send notifications from agents — not called from SPA                                                                                                                                                                                                                                      | P3       |

### Summary

| Category                       | Count                                                                |
| ------------------------------ | -------------------------------------------------------------------- |
| **Fully covered routers**      | 38                                                                   |
| **Partially covered routers**  | 1 (agentEvalExternal, server-only)                                   |
| **Missing (desktop/unused)**   | 5 (comfyui, device, oauthDeviceFlow, agentNotify, agentEvalExternal) |
| **Total TS procedures**        | \~420                                                                |
| **Total Python equivalents**   | \~405                                                                |
| **Total missing (SPA-facing)** | **0**                                                                |

### Priority Breakdown

| Priority          | Domain                                                                                         | Missing |
| ----------------- | ---------------------------------------------------------------------------------------------- | ------- |
| ~~P0 — Critical~~ | ~~`userMemories.ts` (advanced memory queries/tools)~~ ✅ **DONE**                              | 0       |
| ~~P0 — Critical~~ | ~~`task.ts` (dependency graph, checkpoints, reviews, heartbeat, detail)~~ ✅ **DONE**          | 0       |
| ~~P0 — Critical~~ | ~~`agentDocument.ts` (clone, templates, context, upsert)~~ ✅ **DONE**                         | 0       |
| ~~P1 — High~~     | ~~`agentEval.ts` (benchmark/dataset/run management)~~ ✅ **DONE**                              | 0       |
| ~~P1 — High~~     | ~~`ragEval.ts` (dataset/evaluation CRUD)~~ ✅ **DONE**                                         | 0       |
| ~~P1 — High~~     | ~~`agentEvalExternal.ts` (external eval API)~~ ✅ **DONE**                                     | 0       |
| ~~P2 — Medium~~   | ~~`botMessage.ts` (bot platform messaging)~~ ✅ **DONE** — `bot_message.py` stubs              | 0       |
| ~~P2 — Medium~~   | ~~`aiAgent.ts` (advanced client/intervention ops)~~ ✅ **DONE** — 8 endpoints in `ai_agent.py` | 0       |
| ~~P2 — Medium~~   | ~~`file.ts` (knowledge item status/resolve)~~ ✅ **DONE** — aliases in `files.py`              | 0       |
| ~~P2 — Medium~~   | ~~`social.ts` (follow/favorite/like)~~ ✅ **DONE** — `social.py` proxy router                  | 0       |
| ~~P2 — Medium~~   | ~~`user.ts`~~ ✅ **DONE** — fully covered in `user.py` (22 endpoints)                          | 0       |
| ~~P2 — Medium~~   | ~~`admin.ts`~~ ✅ **DONE** — fully covered in `admin.py` (5 endpoints)                         | 0       |
| ~~P3 — Low~~      | ~~`klavis.ts`~~ ✅ **DONE** — `klavis.py`; ~~`aiChat.ts`~~ ✅ **DONE** — `ai_chat.py`          | 0       |
| **P3 — Unused**   | `comfyui.ts`, `device.ts`, `oauthDeviceFlow.ts`, `agentNotify.ts` — not called from SPA        | \~11    |

---

## Remaining Gaps: Services & Infrastructure

### 1. Services — TS directories with no Python equivalent

| TS Service Dir                       | Description                                                                         | Priority | Notes                                                                       |
| ------------------------------------ | ----------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------- |
| `agentDocumentVfs/`                  | Virtual filesystem for agent documents (read/write/list)                            | High     | ✅ DONE — `agent_document_vfs/` (service, types, errors, router)            |
| `agentRuntime/` (77KB)               | Full step-level runner with hooks, skill resolver, tool executor                    | High     | ✅ Hooks, abort, cost, compression, fallback, error classification DONE     |
| `generation/` + `generationBatch.ts` | Title/summary generation, batch processing                                          | Medium   | ✅ DONE — `generation_topics.py`, `generation_batches.py`, `generations.py` |
| `brief/`                             | Brief synthesis from conversation history                                           | Medium   | ✅ DONE — `brief/service.py` + `routers/briefs.py`                          |
| `toolExecution/` (orchestrator)      | Tool execution dispatcher with error classification, device proxy, builtin dispatch | High     | ✅ Error classification DONE — still missing device proxy                   |
| `aiChat/`                            | Chat completions with structured SSE events (text, reasoning, tool_calls, usage)    | Medium   | ✅ DONE — `stream_event/` (types, InMemory manager, SSE endpoint)           |
| `skillMaintainer/`                   | Auto-update skill manifests from market                                             | Low      |                                                                             |
| `systemAgent/`                       | System agent for auto-titles, translation, tag generation                           | Medium   | ✅ DONE — `system_agent/service.py` (title, translate, brief, task)         |
| `discover/`                          | Agent/plugin marketplace discovery service                                          | Low      | Python `market.py` router exists — may need parity check                    |
| `changelog/`                         | Changelog aggregation service                                                       | Low      |                                                                             |
| `gateway/`                           | WebSocket gateway for real-time agent streaming                                     | Medium   | Python uses SSE; WS gateway needed for mobile/desktop reconnect             |
| `onboarding/`                        | User onboarding flow orchestration                                                  | Low      |                                                                             |
| `oauthDeviceFlow/`                   | OAuth 2.0 device authorization flow                                                 | Low      |                                                                             |
| `klavis/`                            | Klavis tool manifest integration                                                    | Low      |                                                                             |
| `email/`                             | Transactional email via Resend/SES                                                  | Low      |                                                                             |
| `riskControl/`                       | Content policy, rate limiting per-model                                             | Medium   | ✅ DONE — `content_policy/service.py` + `tools/_safety.py` rate limiter     |
| `sandbox/`                           | Cloud code sandbox (E2B, Daytona)                                                   | Medium   | Python has local `code_interpreter.py` — no cloud sandbox                   |
| `comfyui/`                           | ComfyUI workflow execution for image gen                                            | Low      |                                                                             |
| `webhookUser/`                       | Webhook-triggered user actions                                                      | Low      |                                                                             |
| `doc/`                               | Documentation service                                                               | Low      |                                                                             |
| `taskReview/`                        | Task review / QA after completion                                                   | Low      | ✅ DONE — `task_review/service.py` (LLM-based rubric eval)                  |
| `taskTemplate/`                      | Reusable task templates                                                             | Low      | ✅ DONE — `task_template/service.py` (daily recs, skill eligibility)        |

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
| `agentDocuments.ts`            | `agent_documents_tool.py` ✅          | —                                               |
| `agentMarketplace.ts`          | **MISSING**                           | Search/install agents from marketplace          |
| `brief.ts`                     | `brief_tool.py` ✅                    | —                                               |
| `cloudSandbox.ts`              | **MISSING**                           | E2B/Daytona cloud sandbox execution             |
| `creds.ts`                     | **MISSING**                           | OAuth credential store for tools                |
| `cron.ts`                      | via `agent_cron_jobs.py` router ✅    | CRUD from agent context via router              |
| `gtd.ts`                       | `gtd_tool.py` ✅                      | —                                               |
| `localSystem.ts`               | **MISSING**                           | Local desktop file/process access (Electron)    |
| `lobeAgent.ts`                 | `lobe_agent_tool.py` ✅               | —                                               |
| `message/` (dispatcher)        | **MISSING**                           | Cross-platform message send (bot platforms)     |
| `remoteDevice.ts`              | **MISSING**                           | Remote device proxy (desktop → cloud)           |
| `task.ts`                      | `task_tool.py` ✅                     | —                                               |
| `webOnboarding.ts`             | **MISSING**                           | Interactive onboarding steps                    |
| `errorClassification.ts`       | `error_classification.py` ✅          | —                                               |
| `deviceProxy.ts`               | **MISSING**                           | Proxy tool calls to Electron desktop client     |
| `builtin.ts` (dispatcher)      | `registry.py` ⚠️ Partial              | TS has richer dispatch with manifest validation |

### 3. Agent Runtime — Feature-level gaps within `agentRuntime/`

| Feature                                                          | TS (`agentRuntime/`, 77KB)                                          | Python (`agent_runtime/`, 7 modules)               | Gap                              |
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

| Model                             | Python Model File   | Service/Router                      | Gap                                                           |
| --------------------------------- | ------------------- | ----------------------------------- | ------------------------------------------------------------- |
| `AgentCronJob`                    | `agent_ops.py` ✅   | ✅ `routers/agent_cron_jobs.py`     | Full CRUD, batch ops, stats                                   |
| `AgentDocument`                   | `agent_ops.py` ✅   | ✅ `agent_document_vfs/`            | Full VFS: list/stat/read/write/mkdir/rename/copy/delete/trash |
| `AgentBotProvider`                | `agent_ops.py` ✅   | ✅ `routers/agent_bot_providers.py` | CRUD + connect/test                                           |
| `UserPersonaDocumentHistory`      | `persona.py` ✅     | ❌ No versioning service            | Need persona diff/snapshot logic                              |
| `MessageGroup`                    | `message_ext.py` ✅ | ✅ Compression group endpoints      | create/cancel/finalize in `messages.py`                       |
| `MessageTts` / `MessageTranslate` | `message_ext.py` ✅ | ✅ Update endpoints exist           | `PUT /{id}/tts`, `PUT /{id}/translate` in `messages.py`       |
| `TopicDocument`                   | `topic_ext.py` ✅   | ❌ No service                       | Document ↔ topic linking                                      |
| `TopicShare`                      | `topic_ext.py` ✅   | ✅ `topics.py` sharing endpoints    | enable/disable/getShareInfo/updateVisibility                  |

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
2. ~~Tool error classification + retry logic~~ ✅ DONE — `error_classification/service.py`
3. ~~Agent Document VFS service~~ ✅ DONE — `agent_document_vfs/` (service, types, errors, router)
4. ~~Structured SSE event types in `aiChat` / streaming~~ ✅ DONE — `stream_event/` (types, InMemory manager, SSE endpoint)
5. ~~Context compression (compactor)~~ ✅ DONE — `context_compressor/service.py`
6. ~~Missing server runtime tools~~ ✅ DONE — `gtd_tool.py`, `task_tool.py`, `brief_tool.py`, `lobe_agent_tool.py`, `agent_documents_tool.py`, `notebook_tool.py`

**High priority (core functionality gaps) — ALL DONE:**

- ~~System Agent Service~~ ✅ DONE — `system_agent/service.py` (title gen, translation, brief synthesis, task handoff)
- ~~Task Review Service~~ ✅ DONE — `task_review/service.py` (LLM-based rubric evaluation)
- ~~Task Template Service~~ ✅ DONE — `task_template/service.py` (daily recommendations, skill eligibility)
- ~~Agent Signal Router~~ ✅ DONE — `routers/agent_signal.py` (emit, policies CRUD, cleanup)
- ~~Brief Service + Router~~ ✅ DONE — `brief/service.py` + `routers/briefs.py` (CRUD, resolve, dismiss)
- ~~Agent Cron Job Router~~ ✅ DONE — `routers/agent_cron_jobs.py` (full CRUD, batch ops, stats)

**Medium priority (improves robustness):**

7. ~~Content policy enforcement~~ ✅ DONE — `content_policy/service.py`
8. ~~Multi-model fallback~~ ✅ DONE — `model_fallback/service.py`
9. ~~Cost tracking per operation~~ ✅ DONE — integrated into `agent_runtime/nodes.py`
10. Cloud sandbox integration (E2B)
11. Generation batch service
12. WebSocket gateway for real-time streaming
13. ~~Risk control service~~ ✅ DONE — `content_policy/` + `tools/_safety.py`

**Low priority (nice-to-have / domain-specific):**

14. ComfyUI, video generation
15. ~~Cron jobs service~~ ✅ DONE — `routers/agent_cron_jobs.py`
16. Credential store tool
17. OAuth device flow
18. Email service
19. Skill maintainer
20. Agent tracing (beyond Langfuse)
21. Subscription / billing

## UI ↔ Python Backend Wiring ✅ Phase 1 COMPLETE

The SPA frontend (React) communicates via TRPC to the TS backend. The TS backend
now reverse-proxies **agent execution** to the Python FastAPI backend when
`PYTHON_BACKEND_URL` is set. The frontend is **unchanged** — it still calls TRPC.

### Architecture

```
SPA (React) → TRPC → TS Backend (Hono) → HTTP proxy → Python Backend (FastAPI)
                       ↕ (DB-only ops stay in TS)
```

### Files created/modified

**TS side (proxy layer):**

- `src/config/db.ts` — added `PYTHON_BACKEND_URL`, `PYTHON_BACKEND_SERVICE_TOKEN` env vars
- `src/server/utils/pythonBackend.ts` — typed `callPythonBackend()` fetch wrapper with auth header forwarding, timeout, error handling
- `src/server/services/pythonAgentProxy.ts` — `PythonAgentProxyService` class with `execAgent`, `execGroupAgent`, `execSubAgentTask`, `interruptTask`; includes camelCase ↔ snake_case key conversion
- `src/server/routers/lambda/aiAgent.ts` — 5 procedures now check `isPythonBackendEnabled()`: `execAgent`, `execAgents`, `execGroupAgent`, `execSubAgentTask`, `interruptTask`

**Python side (auth bridge):**

- `app/config.py` — added `python_backend_service_token` setting
- `app/dependencies.py` — `get_current_user_id` now accepts `X-Service-Token` + `X-Internal-User-Id` headers (constant-time comparison via `hmac.compare_digest`), falling back to OIDC JWT

**Config:**

- `.env.example` — documented `PYTHON_BACKEND_URL` and `PYTHON_BACKEND_SERVICE_TOKEN`
- `python-backend/.env.example` — documented `PYTHON_BACKEND_SERVICE_TOKEN`

### Proxied procedures (Phase 1)

| TRPC Procedure             | Python Endpoint                      | Notes                     |
| -------------------------- | ------------------------------------ | ------------------------- |
| `aiAgent.execAgent`        | `POST /api/ai-agent/exec`            | Full agent orchestration  |
| `aiAgent.execAgents`       | (per-task) `POST /api/ai-agent/exec` | Batch via pMap            |
| `aiAgent.execGroupAgent`   | `POST /api/ai-agent/exec-group`      | Supervisor agent          |
| `aiAgent.execSubAgentTask` | `POST /api/ai-agent/exec-sub-agent`  | Thread-isolated sub-agent |
| `aiAgent.interruptTask`    | `POST /api/ai-agent/interrupt`       | Cancel running op         |

### Not proxied (remain in TS)

- `createOperation`, `startExecution`, `getOperationStatus`, `processHumanIntervention`, `getPendingInterventions` — `AgentRuntimeService` ops (Redis-backed, TS layer)
- `createClientTaskThread`, `createClientGroupAgentTaskThread`, `updateClientTaskThreadStatus` — Thread CRUD (pure DB)
- `getSubAgentTaskStatus` — Thread + Redis polling (pure DB + TS)
- `refreshGatewayToken` — JWT signing (TS layer)

### Activation

```bash
# In TS backend .env:
PYTHON_BACKEND_URL=http://localhost:8000
PYTHON_BACKEND_SERVICE_TOKEN=<shared-secret>

# In Python backend .env:
PYTHON_BACKEND_SERVICE_TOKEN=<same-shared-secret>
```

When `PYTHON_BACKEND_URL` is unset, all procedures use the original TS `AiAgentService` — zero behavior change.

## Structural Improvements ✅ COMPLETE

- All 22 flat service files converted to packages (`<name>/service.py` + `__init__.py`)
- `agent_runtime.py` (1586 lines) split into 7-module package: `state`, `langfuse`, `messages`, `nodes`, `graph`, `checkpointer`, `service`
- `admin.py` moved from `app/` to `app/routers/`
- `main.py` uses explicit router registry with `importlib` (47 routers, grouped by domain)
- All 203 Python files pass `py_compile`
