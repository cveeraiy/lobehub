# Agent Core API Contract

## Purpose

This document defines a portable service/API contract for implementing the core agent platform outside this repository. It is intentionally transport-neutral: an implementation may use REST, GraphQL, RPC, gRPC, WebSocket, SSE, or local IPC as long as the request, response, error, and event semantics are preserved.

This contract complements:

- [System Functional Specification](./sfs.md)
- [Portable Design](./design.md)
- [Implementation Contract](./implementation-contract.md)
- [Runtime Event Protocol](./runtime-event-protocol.md)
- [UI Functional Specification](./ui-functional-spec.md)

## API Principles

All APIs must follow these rules:

- Use stable string IDs for all durable entities.
- Scope all user-owned entities by `userId` or tenant context.
- Accept idempotency keys for mutating APIs that may be retried by clients.
- Return structured errors using the error envelope in this document.
- Return paginated lists with stable cursors or `{ page, pageSize, total }`.
- Never expose provider API keys, OAuth secrets, or local process environment values to the browser.
- For long-running operations, return immediately with an `operationId` and publish progress through the runtime event protocol.
- Treat TRPC procedure names in the current repo as implementation references, not required wire names.

## Common Types

### EntityId

```ts
type EntityId = string;
```

IDs should be opaque to clients. Clients may store and compare them but must not parse meaning from them.

### Timestamp

```ts
type Timestamp = string; // ISO-8601 UTC
```

### PaginationRequest

```ts
interface PaginationRequest {
  page?: number;
  pageSize?: number;
  cursor?: string;
}
```

Rules:

- Offset pagination and cursor pagination are both acceptable.
- If both are provided, cursor pagination wins.
- `pageSize` should default to `20` and should have an implementation-defined max, usually `100`.

### PageResult

```ts
interface PageResult<T> {
  items: T[];
  page?: number;
  pageSize?: number;
  total?: number;
  nextCursor?: string;
}
```

### ErrorEnvelope

```ts
interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: unknown;
    retryable?: boolean;
    provider?: string;
    model?: string;
    operationId?: string;
    requestId?: string;
  };
}
```

Required error codes:

| Code                    | Meaning                                                   |
| ----------------------- | --------------------------------------------------------- |
| `VALIDATION_ERROR`      | Request did not match schema.                             |
| `AUTH_REQUIRED`         | User is not authenticated.                                |
| `FORBIDDEN`             | User cannot access the entity or action.                  |
| `NOT_FOUND`             | Entity does not exist or is not visible to the user.      |
| `CONFLICT`              | Version, lock, idempotency, or state transition conflict. |
| `RATE_LIMITED`          | Caller or provider rate limit exceeded.                   |
| `PROVIDER_AUTH_ERROR`   | Provider credential is missing or invalid.                |
| `PROVIDER_ERROR`        | Provider returned a business or transport error.          |
| `MODEL_UNAVAILABLE`     | Requested provider/model is unavailable.                  |
| `TOOL_NOT_FOUND`        | Tool identifier cannot be resolved.                       |
| `TOOL_EXECUTION_ERROR`  | Tool execution failed.                                    |
| `MCP_CONNECTION_ERROR`  | MCP server could not be contacted.                        |
| `HUMAN_INPUT_REQUIRED`  | Operation is paused for intervention.                     |
| `OPERATION_INTERRUPTED` | Operation was aborted or interrupted.                     |
| `OPERATION_EXPIRED`     | Operation state or stream cannot be resumed.              |
| `INTERNAL_ERROR`        | Unexpected server failure.                                |

## Authentication And Authorization

The current repository uses authenticated TRPC procedures for most user APIs and public procedures for selected config/market/share surfaces. A portable implementation should expose equivalent authorization boundaries:

| API family                                          | Auth requirement                                                |
| --------------------------------------------------- | --------------------------------------------------------------- |
| User chat, agents, memory, tools, tasks, files      | Authenticated user.                                             |
| Provider key/config mutation                        | Authenticated user.                                             |
| Public global config, market listing, shared topics | Public or anonymous with rate limits.                           |
| Runtime worker callbacks                            | Service token or internal network trust.                        |
| Bot/webhook callbacks                               | Platform signature verification plus mapped user/agent binding. |

## Sessions, Topics, Threads, And Messages

### Domain

| Entity  | Meaning                                                                  |
| ------- | ------------------------------------------------------------------------ |
| Session | Long-lived chat workspace for an agent or group.                         |
| Topic   | Conversation branch or grouped message collection inside a session.      |
| Thread  | Isolated sub-task or side conversation linked to a source message/topic. |
| Message | User, assistant, system, or tool message.                                |

### Create Or Ensure Chat Context

```ts
interface ResolveChatContextRequest {
  sessionId?: EntityId;
  agentId?: EntityId;
  groupId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  newTopic?: {
    title: string;
    trigger?: string;
    topicMessageIds?: EntityId[];
    metadata?: Record<string, unknown>;
  };
  newThread?: {
    title?: string;
    sourceMessageId?: EntityId;
    parentThreadId?: EntityId;
    type?: 'isolation' | 'continuation' | 'task';
  };
}
```

Response:

```ts
interface ResolveChatContextResponse {
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  createdTopicId?: EntityId;
  createdThreadId?: EntityId;
}
```

### Send Message

The current repo separates message persistence from runtime execution. A portable implementation may expose one combined endpoint or two endpoints, but it must preserve the same behavior.

```ts
interface SendMessageRequest {
  idempotencyKey?: string;
  agentId?: EntityId;
  groupId?: EntityId;
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  parentMessageId?: EntityId;
  content: string;
  editorData?: unknown;
  files?: Array<{ fileId: EntityId; name?: string; mimeType?: string }>;
  pageSelections?: unknown[];
  preloadMessages?: MessageInput[];
  assistant: {
    provider: string;
    model: string;
    metadata?: Record<string, unknown>;
  };
  runtime?: CreateOperationRequest;
}
```

Response:

```ts
interface SendMessageResponse {
  userMessageId: EntityId;
  assistantMessageId: EntityId;
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  createdTopicId?: EntityId;
  createdThreadId?: EntityId;
  operationId?: EntityId;
  messages?: Message[];
  topics?: PageResult<Topic>;
}
```

Rules:

- The user message must be persisted before runtime execution starts.
- The assistant message should be created in a loading/placeholder state before streaming starts.
- Runtime stream events must reference `assistantMessageId` so clients can patch the visible message.
- If runtime startup fails after message creation, the assistant message must be updated with a structured error.

### List Messages

```ts
interface ListMessagesRequest extends PaginationRequest {
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  agentId?: EntityId;
  groupId?: EntityId;
}
```

Rules:

- Group chat thread queries may include messages from different agents. Do not over-filter by `agentId` when `groupId`/`threadId` is the actual conversation boundary.
- Thread message queries should include source/parent context when the UI needs task provenance.

### Update Assistant Message From Runtime

Runtime workers need an internal operation to patch assistant messages:

```ts
interface PatchAssistantMessageRequest {
  messageId: EntityId;
  operationId: EntityId;
  content?: string;
  reasoning?: string;
  tools?: ChatToolPayload[];
  error?: ErrorEnvelope['error'];
  metadata?: Record<string, unknown>;
  status?: 'loading' | 'streaming' | 'done' | 'error' | 'interrupted';
}
```

## Agent Definitions

### Agent

```ts
interface AgentRecord {
  id: EntityId;
  userId: EntityId;
  title?: string;
  description?: string;
  avatar?: string;
  tags?: string[];
  config: AgentConfig;
  chatConfig?: Record<string, unknown>;
  fewShots?: unknown[];
  knowledgeBaseIds?: EntityId[];
  fileIds?: EntityId[];
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

### AgentConfig

```ts
interface AgentConfig {
  systemRole?: string;
  provider?: string;
  model?: string;
  params?: {
    temperature?: number;
    topP?: number;
    maxTokens?: number;
    presencePenalty?: number;
    frequencyPenalty?: number;
    reasoning?: unknown;
  };
  tools?: {
    builtin?: string[];
    mcp?: string[];
    plugins?: string[];
    skills?: string[];
  };
  memory?: {
    enabled?: boolean;
    layers?: string[];
  };
  security?: {
    approvalRequiredTools?: string[];
    blacklist?: string[];
  };
}
```

Required APIs:

| Operation            | Request                   | Response                  |
| -------------------- | ------------------------- | ------------------------- |
| List agents          | Filters, pagination       | `PageResult<AgentRecord>` |
| Get agent            | `{ id }`                  | `AgentRecord`             |
| Create agent         | Partial agent fields      | `AgentRecord`             |
| Update agent         | `{ id, patch, version? }` | `AgentRecord`             |
| Delete agent         | `{ id }`                  | `{ success: true }`       |
| Touch agent activity | `{ id }`                  | `{ updatedAt }`           |

## Group Agents

```ts
interface GroupRecord {
  id: EntityId;
  userId: EntityId;
  name: string;
  description?: string;
  config?: Record<string, unknown>;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

interface GroupAgentBinding {
  groupId: EntityId;
  agentId: EntityId;
  role?: 'supervisor' | 'member' | 'worker';
  order?: number;
  config?: Record<string, unknown>;
}
```

Required APIs:

- Create/update/delete/list groups.
- Add/remove/reorder group agents.
- Fetch a group with agent bindings.
- Send group chat messages using the same `SendMessageRequest` shape with `groupId`.
- Create client task threads for group workers.

### Create Client Group Task Thread

```ts
interface CreateClientGroupTaskThreadRequest {
  groupId: EntityId;
  subAgentId: EntityId;
  topicId: EntityId;
  parentMessageId: EntityId;
  instruction: string;
  title?: string;
}
```

Response:

```ts
interface CreateClientTaskThreadResponse {
  success: boolean;
  threadId: EntityId;
  userMessageId: EntityId;
  startedAt: Timestamp;
  threadMessages: Message[];
  messages: Message[];
}
```

## Runtime Operations

### CreateOperationRequest

```ts
interface CreateOperationRequest {
  agentId?: EntityId;
  groupId?: EntityId;
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  userMessageId?: EntityId;
  assistantMessageId?: EntityId;
  provider: string;
  model: string;
  input: {
    messages?: Message[];
    prompt?: string;
    attachments?: unknown[];
  };
  context?: {
    locale?: string;
    timezone?: string;
    platform?: 'web' | 'desktop' | 'mobile' | 'bot' | 'api';
    source?: string;
  };
  options?: {
    maxSteps?: number;
    forceFinish?: boolean;
    stream?: boolean;
    trace?: boolean;
    runInClient?: boolean;
  };
}
```

### OperationRecord

```ts
interface OperationRecord {
  operationId: EntityId;
  status:
    | 'idle'
    | 'queued'
    | 'running'
    | 'waiting_for_human'
    | 'done'
    | 'error'
    | 'interrupted'
    | 'expired';
  agentId?: EntityId;
  groupId?: EntityId;
  sessionId?: EntityId;
  topicId?: EntityId;
  threadId?: EntityId;
  userMessageId?: EntityId;
  assistantMessageId?: EntityId;
  provider: string;
  model: string;
  stepCount: number;
  usage?: Usage;
  cost?: Cost;
  error?: ErrorEnvelope['error'];
  createdAt: Timestamp;
  updatedAt: Timestamp;
  expiresAt?: Timestamp;
}
```

Required APIs:

| Operation               | Semantics                                                             |
| ----------------------- | --------------------------------------------------------------------- |
| Create operation        | Persist immutable initial context, tool snapshots, and initial state. |
| Start operation         | Schedule or synchronously execute first step.                         |
| Get operation           | Return current operation record and compact state.                    |
| Stream operation        | Subscribe to event protocol by `operationId`.                         |
| Replay operation events | Return persisted event page after a sequence number.                  |
| Resume operation        | Continue from waiting/interrupted states when allowed.                |
| Interrupt operation     | Request cooperative abort.                                            |
| Delete/expire operation | Mark expired and optionally purge stream payloads after retention.    |

## Human Intervention

### Submit Human Prompt

```ts
interface SubmitHumanPromptRequest {
  operationId: EntityId;
  response: string;
}
```

### Submit Human Selection

```ts
interface SubmitHumanSelectionRequest {
  operationId: EntityId;
  selected: string | string[];
}
```

### Approve Tools

```ts
interface ApproveToolsRequest {
  operationId: EntityId;
  approvedToolCallIds: EntityId[];
  rejectedToolCallIds?: EntityId[];
  rememberDecision?: boolean;
}
```

Rules:

- These APIs are valid only when operation status is `waiting_for_human`.
- Responses must append a runtime event and schedule the next step.
- Rejected tools must become cancelled tool results, not silently disappear.

## Provider And Model APIs

### ProviderRecord

```ts
interface ProviderRecord {
  id: string;
  name: string;
  enabled: boolean;
  source: 'builtin' | 'custom' | 'user' | 'system';
  config?: Record<string, unknown>;
  capabilities?: ProviderCapabilities;
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
}
```

### ModelRecord

```ts
interface ModelRecord {
  id: string;
  providerId: string;
  displayName?: string;
  enabled: boolean;
  abilities: {
    chat?: boolean;
    tools?: boolean;
    vision?: boolean;
    reasoning?: boolean;
    embedding?: boolean;
    image?: boolean;
    structuredOutput?: boolean;
  };
  contextWindow?: number;
  maxOutput?: number;
  pricing?: Record<string, unknown>;
}
```

Required APIs:

- List configured providers.
- Create/update/delete custom provider config.
- Test provider credential.
- List local/static model metadata.
- Fetch live provider models when supported.
- Enable/disable models.
- Resolve default provider/model for a user/agent.

## Model Runtime APIs

These are usually backend-internal, but portable implementations should expose them as service interfaces:

```ts
interface ChatCompletionRequest {
  provider: string;
  model: string;
  messages: ModelMessage[];
  tools?: UniformModelTool[];
  toolChoice?: 'auto' | 'none' | { name: string };
  stream?: boolean;
  responseFormat?: unknown;
  params?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
```

Response for non-streaming:

```ts
interface ChatCompletionResponse {
  message: ModelMessage;
  toolCalls?: ChatToolPayload[];
  usage?: Usage;
  finishReason?: string;
  raw?: unknown;
}
```

Streaming responses must use [Runtime Event Protocol](./runtime-event-protocol.md) or a lower-level provider stream normalized by [Provider Adapter Specification](./provider-adapter-spec.md).

## Tools, MCP, And Skills

### List Enabled Tools For Runtime

```ts
interface ResolveToolsRequest {
  agentId?: EntityId;
  groupId?: EntityId;
  sessionId?: EntityId;
  enabledBuiltinTools?: string[];
  enabledMcpServers?: string[];
  enabledSkills?: string[];
  platform?: 'web' | 'desktop' | 'server' | 'bot';
}
```

Response:

```ts
interface ResolveToolsResponse {
  operationToolSet: OperationToolSet;
  manifests: Record<string, ToolManifest>;
  modelTools: UniformModelTool[];
  sourceMap: Record<string, ToolSource>;
}
```

### MCP APIs

Supported client params:

```ts
type MCPClientParams =
  | {
      type: 'http';
      name: string;
      url: string;
      auth?: { type: string; token?: string; headers?: Record<string, string> };
      headers?: Record<string, string>;
    }
  | {
      type: 'stdio';
      name: string;
      command: string;
      args?: string[];
    };
```

Required APIs:

| Operation               | Request                                | Response               |
| ----------------------- | -------------------------------------- | ---------------------- |
| Get streamable manifest | identifier, URL, metadata/auth/headers | MCP server manifest    |
| List tools              | `MCPClientParams`                      | MCP tool list          |
| List resources          | `MCPClientParams`                      | MCP resource list      |
| List prompts            | `MCPClientParams`                      | MCP prompt list        |
| Call tool               | `{ params, toolName, args, meta? }`    | normalized tool result |

Rules:

- `stdio` MCP is allowed only in local/desktop/server environments that can launch processes.
- Web/browser clients must not execute `stdio` directly.
- MCP content blocks that contain files/images must be normalized into durable file resources before returning to the chat UI.

### Skills APIs

Required APIs:

- List installed skills.
- List marketplace/public skills.
- Install/update/delete skill.
- Activate skill for an operation.
- Read skill references.
- Execute skill scripts/commands where allowed.
- Export generated files.

Skills should expose manifests and resources independently from the runtime that executes them.

## Memory APIs

Memory surfaces must support layered query, detail, semantic search, extraction, and re-embedding.

### QueryMemoryRequest

```ts
interface QueryMemoryRequest extends PaginationRequest {
  layer?: 'identity' | 'preference' | 'activity' | 'experience' | 'context' | string;
  q?: string;
  tags?: string[];
  types?: string[];
  status?: string[];
  categories?: string[];
  relationships?: string[];
  sort?:
    | 'capturedAt'
    | 'startsAt'
    | 'scoreConfidence'
    | 'scoreImpact'
    | 'scorePriority'
    | 'scoreUrgency'
    | 'type';
  order?: 'asc' | 'desc';
}
```

Required APIs:

- Query all memory layers.
- Query activities.
- Query experiences.
- Query identities.
- Query identities for injection.
- Query identity roles.
- Query tags.
- Query taxonomy options.
- Get memory detail by `{ id, layer }`.
- Search memories semantically for context injection.
- Create/update/delete memory records.
- Extract memories from messages.
- Re-embed memory records.

Rules:

- Memory records must remain user-scoped.
- Search APIs must accept embedding model/provider configuration indirectly through user settings or runtime config.
- UI query APIs should return empty lists on recoverable query failures only if the product intentionally hides backend failures; otherwise use `ErrorEnvelope`.

## Knowledge, Files, And RAG APIs

Required APIs:

- Upload file or create upload URL.
- Create document record.
- Parse document.
- Chunk document.
- Embed chunks.
- Create/update/delete knowledge base.
- Attach/detach files or knowledge bases to agents.
- Search chunks by query/embedding.
- Return source citations for injected chunks.

Portable response for search:

```ts
interface KnowledgeSearchResult {
  chunkId: EntityId;
  documentId?: EntityId;
  fileId?: EntityId;
  knowledgeBaseId?: EntityId;
  text: string;
  similarity?: number;
  metadata?: Record<string, unknown>;
}
```

## Tasks And Async Jobs

Required APIs:

- Create/update/delete task.
- Link task to topics, documents, files, or agents.
- Create task dependency.
- Start async task run.
- Get async task status.
- Cancel async task.
- Append task comments/events.
- Create client-side task thread for local execution.

Async task status:

```ts
type AsyncTaskStatus = 'pending' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
```

## Agent Signal APIs

Agent Signal is the background semantic event pipeline. Portable APIs:

- Ingest source event.
- List signal definitions.
- Create/update signal.
- List signal runs.
- Get signal run detail.
- Retry signal run.
- Disable signal.

Source event envelope:

```ts
interface AgentSignalSourceEvent {
  source: 'runtime' | 'client' | 'bot' | 'feedback' | 'system' | string;
  type: string;
  userId?: EntityId;
  agentId?: EntityId;
  sessionId?: EntityId;
  topicId?: EntityId;
  operationId?: EntityId;
  payload: unknown;
  occurredAt: Timestamp;
}
```

## Tracing APIs

Required APIs:

- Create execution snapshot.
- List snapshots by operation/session/topic.
- Get snapshot detail.
- Compare snapshots.
- Delete snapshots after retention.

Trace snapshots must not expose provider secrets or raw sensitive tool arguments unless explicitly enabled for privileged users.

## Audit And Usage APIs

Required APIs:

- Record model usage.
- Record tool usage.
- Record provider errors.
- Record user approvals/rejections.
- Query user-level usage summaries.
- Query operation-level usage and cost.

Usage:

```ts
interface Usage {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  cachedInputTokens?: number;
  reasoningTokens?: number;
  toolCalls?: number;
  llmCalls?: number;
}
```

Cost:

```ts
interface Cost {
  amount: number;
  currency?: string;
  breakdown?: Record<string, number>;
}
```

## UI Service Adapter Requirements

A React UI port should depend on service adapters with these capabilities:

- `chatService`: send message, list messages, patch/retry/delete messages.
- `operationService`: create/start/stream/replay/resume/interrupt operations.
- `agentService`: CRUD agents and agent settings.
- `groupService`: CRUD groups and group members.
- `providerService`: providers, models, credential tests.
- `toolService`: builtin tools, MCP tools, skill tools, tool call details.
- `memoryService`: query/search/detail/update/extract/re-embed memory.
- `resourceService`: files, documents, knowledge bases, chunks.
- `taskService`: tasks, dependencies, async task runs, client task threads.
- `traceService`: operation snapshots and step inspection.
- `signalService`: signal runs and outcomes where surfaced.

The UI must not import backend implementation objects directly.
