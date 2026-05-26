# Agent Runtime Event Protocol

## Purpose

This document defines the portable event protocol used to stream, persist, replay, and inspect agent runtime execution.

It combines two concerns:

- **Live stream events** consumed by chat UI, bot bridges, desktop clients, and workers.
- **Durable runtime events** persisted for replay, reconnect, tracing, debugging, and conformance tests.

## Transport

Implementations may use:

- Server-Sent Events
- WebSocket
- fetch streaming
- message queue fan-out
- local IPC
- polling with event sequence replay

The wire transport is not normative. The event envelope and ordering rules are normative.

## Event Envelope

Every event must use this envelope:

```ts
interface RuntimeEvent<T = unknown> {
  id: string;
  operationId: string;
  sequence: number;
  type: RuntimeEventType;
  phase?: AgentRuntimePhase;
  stepIndex?: number;
  timestamp: string;
  payload: T;
  metadata?: Record<string, unknown>;
}
```

Rules:

- `id` is globally unique or unique within the operation.
- `sequence` starts at `1` per operation and increments by exactly one for persisted events.
- Live-only heartbeat events may omit persistence but must not reuse sequence numbers.
- `timestamp` is ISO-8601 UTC.
- `operationId` must be present on every event.
- `payload` must be JSON-serializable.

## Event Types

```ts
type RuntimeEventType =
  | 'operation.created'
  | 'operation.queued'
  | 'operation.started'
  | 'operation.state_changed'
  | 'operation.completed'
  | 'operation.failed'
  | 'operation.interrupted'
  | 'operation.expired'
  | 'step.started'
  | 'step.completed'
  | 'step.failed'
  | 'llm.started'
  | 'llm.text_delta'
  | 'llm.reasoning_delta'
  | 'llm.tool_call_delta'
  | 'llm.completed'
  | 'llm.failed'
  | 'tool.discovered'
  | 'tool.call_started'
  | 'tool.call_delta'
  | 'tool.call_completed'
  | 'tool.call_failed'
  | 'tool.call_cancelled'
  | 'skill.activated'
  | 'mcp.connected'
  | 'mcp.failed'
  | 'memory.search_started'
  | 'memory.search_completed'
  | 'memory.extraction_started'
  | 'memory.extraction_completed'
  | 'context.assembled'
  | 'context.compressed'
  | 'human.approval_requested'
  | 'human.prompt_requested'
  | 'human.select_requested'
  | 'human.response_received'
  | 'task.started'
  | 'task.completed'
  | 'task.failed'
  | 'trace.snapshot_created'
  | 'usage.updated'
  | 'stream.heartbeat';
```

Implementations may add namespaced extension events, for example `vendor.foo`, but must not change the meaning of the standard events.

## Runtime Phases

```ts
type AgentRuntimePhase =
  | 'init'
  | 'user_input'
  | 'llm_result'
  | 'tool_result'
  | 'tools_batch_result'
  | 'task_result'
  | 'tasks_batch_result'
  | 'human_response'
  | 'human_approved_tool'
  | 'human_abort'
  | 'compression_result'
  | 'error';
```

The phase describes what input the agent runner will see next. Event `type` describes what happened externally.

## Operation Lifecycle

Required event order:

```text
operation.created
operation.queued?
operation.started
step.started
...
step.completed | step.failed
...
operation.completed | operation.failed | operation.interrupted | operation.expired
```

Rules:

- `operation.created` must be persisted before any LLM/tool event.
- `operation.started` must be emitted once for each execution attempt.
- A resumed operation may emit another `operation.started` with metadata `{ resumed: true }`.
- Exactly one terminal operation event should be emitted.
- Terminal events must include final status, usage, cost, and error when present.

## Step Events

### step.started

```ts
interface StepStartedPayload {
  stepIndex: number;
  instructionType?: string;
  stepLabel?: string;
  stateStatus: string;
}
```

### step.completed

```ts
interface StepCompletedPayload {
  stepIndex: number;
  instructionType?: string;
  nextPhase?: AgentRuntimePhase;
  stateStatus: string;
  elapsedMs?: number;
}
```

### step.failed

```ts
interface StepFailedPayload {
  stepIndex: number;
  instructionType?: string;
  error: RuntimeErrorPayload;
  recoverable?: boolean;
}
```

## LLM Events

### llm.started

```ts
interface LLMStartedPayload {
  provider: string;
  model: string;
  apiMode?: 'chatCompletion' | 'responses' | string;
  messageCount?: number;
  toolCount?: number;
  params?: Record<string, unknown>;
}
```

### llm.text_delta

```ts
interface LLMTextDeltaPayload {
  messageId?: string;
  delta: string;
  accumulated?: string;
}
```

Rules:

- `delta` is the incremental text chunk.
- `accumulated` is optional. If present, clients should prefer it for idempotent rendering.
- Empty deltas should not be emitted unless needed as a provider compatibility marker.

### llm.reasoning_delta

```ts
interface LLMReasoningDeltaPayload {
  messageId?: string;
  delta: string;
  accumulated?: string;
  visibility?: 'hidden' | 'collapsed' | 'visible';
}
```

### llm.tool_call_delta

```ts
interface LLMToolCallDeltaPayload {
  index?: number;
  id?: string;
  name?: string;
  argumentsDelta?: string;
  argumentsAccumulated?: string;
  modelToolName?: string;
}
```

Rules:

- Tool-call arguments may arrive as partial JSON strings.
- The provider adapter must produce a final parsed object before `llm.completed` or before tool execution.
- Invalid partial JSON must not fail the stream until final parse is required.

### llm.completed

```ts
interface LLMCompletedPayload {
  messageId?: string;
  content?: string;
  reasoning?: string;
  toolCalls?: ChatToolPayload[];
  usage?: Usage;
  finishReason?: string;
  rawFinishReason?: string;
  elapsedMs?: number;
}
```

## Tool Events

### tool.call_started

```ts
interface ToolCallStartedPayload {
  toolCallId: string;
  modelToolName: string;
  identifier: string;
  source: 'builtin' | 'mcp' | 'plugin' | 'skill' | 'client' | 'server' | 'local' | string;
  displayName?: string;
  arguments?: unknown;
  requiresApproval?: boolean;
}
```

### tool.call_completed

```ts
interface ToolCallCompletedPayload {
  toolCallId: string;
  identifier: string;
  result: unknown;
  content?: string;
  artifacts?: RuntimeArtifact[];
  elapsedMs?: number;
}
```

### tool.call_failed

```ts
interface ToolCallFailedPayload {
  toolCallId: string;
  identifier: string;
  error: RuntimeErrorPayload;
  elapsedMs?: number;
}
```

### tool.call_cancelled

```ts
interface ToolCallCancelledPayload {
  toolCallId: string;
  identifier: string;
  reason: 'user_rejected' | 'operation_interrupted' | 'timeout' | 'policy' | string;
}
```

Rules:

- Every started tool call must end in completed, failed, or cancelled.
- Tool events must include both the model-facing tool name and the original tool identifier when available.
- Tool results must be serializable. Binary data must be stored as artifacts/files and referenced by ID or URL.

## Skill Events

```ts
interface SkillActivatedPayload {
  skillId: string;
  identifier: string;
  name?: string;
  toolIdentifiers?: string[];
  references?: Array<{ id: string; title?: string; type?: string }>;
}
```

Skill activation should be emitted when a skill becomes part of the operation context, not every time its prompt text is read.

## MCP Events

```ts
interface MCPConnectedPayload {
  serverId?: string;
  name: string;
  type: 'http' | 'stdio';
  toolCount?: number;
  resourceCount?: number;
  promptCount?: number;
}

interface MCPFailedPayload {
  serverId?: string;
  name: string;
  type: 'http' | 'stdio';
  error: RuntimeErrorPayload;
}
```

## Memory Events

### memory.search_started

```ts
interface MemorySearchStartedPayload {
  query: string;
  layers?: string[];
  limit?: number;
}
```

### memory.search_completed

```ts
interface MemorySearchCompletedPayload {
  query: string;
  results: Array<{
    id: string;
    layer: string;
    title?: string;
    content?: string;
    score?: number;
    tags?: string[];
  }>;
  injected?: boolean;
  elapsedMs?: number;
}
```

### memory.extraction_completed

```ts
interface MemoryExtractionCompletedPayload {
  sourceMessageIds?: string[];
  created?: number;
  updated?: number;
  ignored?: number;
  records?: Array<{ id: string; layer: string; action: 'created' | 'updated' | 'ignored' }>;
}
```

## Context Events

### context.assembled

```ts
interface ContextAssembledPayload {
  messageCount: number;
  systemPromptIncluded?: boolean;
  memoryIncluded?: boolean;
  knowledgeIncluded?: boolean;
  toolCount?: number;
  skillCount?: number;
  tokenEstimate?: number;
}
```

### context.compressed

```ts
interface ContextCompressedPayload {
  previousMessageCount: number;
  nextMessageCount: number;
  summaryMessageId?: string;
  tokenEstimateBefore?: number;
  tokenEstimateAfter?: number;
}
```

## Human Intervention Events

### human.approval_requested

```ts
interface HumanApprovalRequestedPayload {
  prompt?: string;
  reason?: string;
  pendingToolCalls: ChatToolPayload[];
  policy?: Record<string, unknown>;
}
```

### human.prompt_requested

```ts
interface HumanPromptRequestedPayload {
  prompt: string;
  reason?: string;
  metadata?: Record<string, unknown>;
}
```

### human.select_requested

```ts
interface HumanSelectRequestedPayload {
  prompt?: string;
  options: Array<{ label: string; value: string }>;
  multi?: boolean;
  reason?: string;
  metadata?: Record<string, unknown>;
}
```

### human.response_received

```ts
interface HumanResponseReceivedPayload {
  kind: 'approval' | 'prompt' | 'select' | 'abort';
  approvedToolCallIds?: string[];
  rejectedToolCallIds?: string[];
  response?: string;
  selected?: string | string[];
}
```

Rules:

- When a human request event is emitted, operation status must become `waiting_for_human`.
- The stream should remain reconnectable while waiting.
- Human responses must be persisted as events before resuming.

## Task Events

```ts
interface TaskStartedPayload {
  taskId?: string;
  threadId?: string;
  title?: string;
  instruction?: string;
  runInClient?: boolean;
}

interface TaskCompletedPayload {
  taskId?: string;
  threadId?: string;
  result?: unknown;
  elapsedMs?: number;
}

interface TaskFailedPayload {
  taskId?: string;
  threadId?: string;
  error: RuntimeErrorPayload;
}
```

## Usage Events

```ts
interface UsageUpdatedPayload {
  stepIndex?: number;
  usage: Usage;
  cost?: Cost;
  delta?: {
    usage?: Usage;
    cost?: Cost;
  };
}
```

Clients should treat usage updates as advisory until the terminal operation event.

## Terminal Events

### operation.completed

```ts
interface OperationCompletedPayload {
  status: 'done';
  reason?: string;
  finalMessageId?: string;
  lastAssistantContent?: string;
  usage?: Usage;
  cost?: Cost;
  durationMs?: number;
}
```

### operation.failed

```ts
interface OperationFailedPayload {
  status: 'error';
  error: RuntimeErrorPayload;
  usage?: Usage;
  cost?: Cost;
  durationMs?: number;
}
```

### operation.interrupted

```ts
interface OperationInterruptedPayload {
  status: 'interrupted';
  reason: string;
  canResume: boolean;
  interruptedAt: string;
}
```

## Error Payload

```ts
interface RuntimeErrorPayload {
  code: string;
  message: string;
  details?: unknown;
  retryable?: boolean;
  provider?: string;
  model?: string;
  toolIdentifier?: string;
  raw?: unknown;
}
```

## Artifact Payload

```ts
interface RuntimeArtifact {
  id: string;
  kind: 'file' | 'image' | 'document' | 'link' | 'json' | string;
  name?: string;
  mimeType?: string;
  url?: string;
  fileId?: string;
  metadata?: Record<string, unknown>;
}
```

## Replay And Reconnect

Clients must be able to reconnect using:

```ts
interface ReplayEventsRequest {
  operationId: string;
  afterSequence?: number;
  limit?: number;
}
```

Response:

```ts
interface ReplayEventsResponse {
  operationId: string;
  events: RuntimeEvent[];
  latestSequence: number;
  terminal: boolean;
}
```

Rules:

- If `afterSequence` is omitted, replay starts from the beginning or from a retention checkpoint.
- If requested events are no longer retained, return `OPERATION_EXPIRED`.
- Replayed events must be byte-for-byte equivalent where possible, except for redacted sensitive fields.

## Client Rendering Rules

The UI should:

- Render text deltas into the assistant message associated with the operation.
- Render reasoning deltas separately from final content.
- Render tool calls as structured blocks with status transitions.
- Show human intervention controls when the operation is waiting.
- Use replay after reconnect before attaching to live events.
- Treat terminal events as authoritative for final status.

## Persistence Rules

Persist at minimum:

- all operation lifecycle events
- all step start/complete/fail events
- all LLM completed/failed events
- all tool start/complete/fail/cancel events
- human request/response events
- terminal operation event

Text deltas may be compacted after the assistant message has been finalized, but only if replay can reconstruct the final user-visible state.
