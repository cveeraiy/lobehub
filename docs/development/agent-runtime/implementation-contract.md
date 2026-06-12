# Agent Runtime Implementation Contract

## Purpose

This document defines the language-neutral contract required to implement a LobeHub-compatible agent runtime. It narrows the broader SFS and design docs into the minimum interoperable surfaces needed for:

- model/provider selection
- builtin tool and skill execution
- MCP tool discovery and invocation
- context assembly
- operation persistence and streaming
- human intervention
- cross-language conformance testing

Use this document with:

- `docs/development/agent-runtime/sfs.md`
- `docs/development/agent-runtime/design.md`
- `docs/development/agent-runtime/ui-functional-spec.md`
- `docs/development/agent-runtime/api-contract.md`
- `docs/development/agent-runtime/runtime-event-protocol.md`
- `docs/development/agent-runtime/provider-adapter-spec.md`
- `docs/development/agent-runtime/persistence-ddl-spec.md`
- `docs/development/agent-runtime/conformance-test-plan.md`

## Compatibility Levels

### Level 0: Demo Runtime

Required for demonstrating an agent with model selection, MCP, and builtin skills.

- single-agent chat loop
- model/provider selection
- function/tool calling
- builtin skill tool manifest and executor
- MCP list-tools and call-tool flow
- in-memory operation state
- streaming text/tool events
- basic human approval for sensitive tools

### Level 1: Portable Runtime

Required for a production reimplementation in another language.

- durable operation state
- resumable stream/event history
- immutable operation tool/skill snapshots
- context-engine processors and providers
- cost/usage tracking
- max-step and force-finish behavior
- structured error normalization
- conformance fixtures

### Level 2: Full LobeHub Runtime

Required for feature parity.

- graph agent execution
- group orchestration
- task execution and client task dispatch
- context compression
- memory retrieval and writes
- agent documents
- Agent Signal hooks
- tracing snapshots
- cloud/local runtime environments

## Core Domain Objects

All persisted objects MUST be JSON-serializable. Implementations MAY use language-native classes internally, but persisted state and stream payloads MUST follow these shapes.

### AgentRuntimeContext

```ts
interface AgentRuntimeContext {
  operationId?: string;
  phase:
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
  payload?: unknown;
  initialContext?: RuntimeInitialContext;
  stepContext?: RuntimeStepContext;
  stepUsage?: unknown;
  metadata?: Record<string, unknown>;
  session?: {
    sessionId: string;
    status: AgentState['status'];
    stepCount: number;
    messageCount: number;
  };
}
```

Rules:

- `phase` is the only required field.
- `initialContext` is captured once at operation creation and treated as immutable.
- `stepContext` is recomputed at every runtime step.
- `payload` MUST match the current phase.

### AgentState

```ts
interface AgentState {
  operationId: string;
  status: 'idle' | 'running' | 'waiting_for_human' | 'done' | 'error' | 'interrupted';
  messages: unknown[];
  stepCount: number;
  createdAt: string;
  lastModified: string;
  usage: Usage;
  cost: Cost;
  modelRuntimeConfig?: ModelRuntimeConfig;
  systemRole?: string;
  toolManifestMap: Record<string, ToolManifest>;
  tools?: UniformTool[];
  operationToolSet?: OperationToolSet;
  toolSourceMap?: Record<string, ToolSource>;
  toolExecutorMap?: Record<string, ToolExecutor>;
  activatedStepTools?: ActivatedStepTool[];
  activatedStepSkills?: ActivatedStepSkill[];
  pendingToolsCalling?: ChatToolPayload[];
  pendingHumanPrompt?: { prompt: string; metadata?: Record<string, unknown> };
  pendingHumanSelect?: {
    prompt?: string;
    options: Array<{ label: string; value: string }>;
    multi?: boolean;
    metadata?: Record<string, unknown>;
  };
  userInterventionConfig?: UserInterventionConfig;
  securityBlacklist?: SecurityBlacklistConfig;
  maxSteps?: number;
  forceFinish?: boolean;
  costLimit?: CostLimit;
  error?: unknown;
  interruption?: {
    reason: string;
    interruptedAt: string;
    interruptedInstruction?: unknown;
    canResume: boolean;
  };
  metadata?: Record<string, unknown>;
}
```

Rules:

- `operationToolSet` is immutable after operation creation.
- `toolManifestMap` MUST include all manifests needed to resolve model tool-call names back to original tool identifiers.
- `activatedStepTools` and `activatedStepSkills` are cumulative records.
- `pendingToolsCalling`, `pendingHumanPrompt`, and `pendingHumanSelect` are only valid when `status` is `waiting_for_human`.

### ModelRuntimeConfig

```ts
interface ModelRuntimeConfig {
  provider: string;
  model: string;
  compressionModel?: {
    provider: string;
    model: string;
  };
}
```

Rules:

- Provider-specific protocol details MUST live behind the model runtime adapter.
- Runtime code MUST pass provider/model identifiers through unchanged.
- Tool support, structured output support, context window, reasoning support, and multimodal support MUST be exposed through model capability metadata.

## Agent Contract

```ts
interface Agent {
  runner(
    context: AgentRuntimeContext,
    state: AgentState,
  ): Promise<AgentInstruction | AgentInstruction[]>;
  modelRuntime?: (payload: unknown) => AsyncIterable<unknown>;
  tools?: Record<string, (args: unknown) => Promise<unknown>>;
  executors?: Partial<Record<AgentInstruction['type'], InstructionExecutor>>;
  calculateUsage?: (
    operationType: 'llm' | 'tool' | 'human_interaction',
    operationResult: unknown,
    previousUsage: Usage,
  ) => Usage;
  calculateCost?: (context: CostCalculationContext) => Cost;
}
```

Rules:

- Agents are stateless decision components.
- The runner MUST return serializable instruction objects.
- Runtime implementations MUST NOT depend on concrete agent classes.

## Instruction Contract

Every instruction MAY include:

```ts
interface AgentInstructionBase {
  stepLabel?: string;
}
```

Supported instruction types:

```ts
type AgentInstruction =
  | { type: 'call_llm'; payload: CallLLMPayload; stepLabel?: string }
  | { type: 'call_tool'; payload: CallToolPayload; stepLabel?: string }
  | { type: 'call_tools_batch'; payload: CallToolsBatchPayload; stepLabel?: string }
  | { type: 'resolve_aborted_tools'; payload: ResolveAbortedToolsPayload; stepLabel?: string }
  | { type: 'exec_task'; payload: ExecTaskPayload; stepLabel?: string }
  | { type: 'exec_tasks'; payload: ExecTasksPayload; stepLabel?: string }
  | { type: 'exec_client_task'; payload: ExecTaskPayload; stepLabel?: string }
  | { type: 'exec_client_tasks'; payload: ExecTasksPayload; stepLabel?: string }
  | {
      type: 'request_human_prompt';
      prompt: string;
      reason?: string;
      metadata?: Record<string, unknown>;
      stepLabel?: string;
    }
  | {
      type: 'request_human_select';
      prompt?: string;
      options: Array<{ label: string; value: string }>;
      multi?: boolean;
      reason?: string;
      metadata?: Record<string, unknown>;
      stepLabel?: string;
    }
  | {
      type: 'request_human_approve';
      pendingToolsCalling: ChatToolPayload[];
      reason?: string;
      skipCreateToolMessage?: boolean;
      stepLabel?: string;
    }
  | { type: 'compress_context'; payload: CompressContextPayload; stepLabel?: string }
  | { type: 'finish'; reason: FinishReason; reasonDetail?: string; stepLabel?: string };
```

Minimum Level 0 implementations MUST support:

- `call_llm`
- `call_tool`
- `call_tools_batch`
- `request_human_approve`
- `finish`

## Tool Contract

### Tool Manifest

```ts
interface ToolManifest {
  identifier: string;
  type?: 'default' | 'standalone' | 'markdown' | 'mcp' | 'builtin';
  meta: {
    title?: string;
    description?: string;
    avatar?: string;
    [key: string]: unknown;
  };
  systemRole?: string;
  api: Array<{
    name: string;
    description: string;
    parameters: Record<string, unknown>;
    humanIntervention?: HumanInterventionPolicy;
    url?: string;
  }>;
  mcpParams?: MCPClientParams;
}
```

### Uniform Model Tool

```ts
interface UniformTool {
  type: 'function';
  function: {
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  };
}
```

### OperationToolSet

```ts
type ToolSource = 'builtin' | 'client' | 'mcp' | 'klavis' | 'lobehubSkill';
type ToolExecutor = 'client' | 'server';

interface OperationToolSet {
  enabledToolIds: string[];
  tools: UniformTool[];
  manifestMap: Record<string, ToolManifest>;
  sourceMap: Record<string, ToolSource>;
  executorMap?: Record<string, ToolExecutor>;
}
```

Rules:

- Tool resolution MUST start from the immutable `OperationToolSet`.
- Step-level activations MAY add tools, but MUST NOT mutate the operation snapshot.
- A force-finish step MAY deactivate all model tools while retaining manifests for name resolution.
- Tool results SHOULD be truncated according to runtime policy before being appended back into model context.

### Tool Name Mapping

Model-facing tool names MUST be generated as:

```text
{identifier}____{apiName}[____{type}]
```

Rules:

- Omit `type` when it is `builtin` or `default`.
- If the generated name is 64 characters or longer, replace `apiName` with `MD5HASH_{first_12_hex_chars}`.
- If still 64 characters or longer, also replace `identifier` with `MD5HASH_{first_12_hex_chars}`.
- Reverse mapping MUST use `manifestMap` to recover original `identifier` and `apiName`.

### ChatToolPayload

```ts
interface ChatToolPayload {
  id: string;
  identifier: string;
  apiName: string;
  arguments: string;
  type: 'builtin' | 'mcp' | 'default' | 'markdown' | 'standalone' | string;
  thoughtSignature?: string;
}
```

Rules:

- `arguments` is the JSON string emitted by the model.
- `thoughtSignature` MUST be round-tripped for providers that require it.

## MCP Contract

MCP is a tool source. After discovery and normalization, MCP tools MUST be indistinguishable from other tools to the core runtime.

### MCPClientParams

```ts
type MCPClientParams =
  | { type: 'stdio'; name: string; command: string; args?: string[]; env?: Record<string, string> }
  | { type: 'http'; name: string; url: string; auth?: MCPAuth; headers?: Record<string, string> }
  | { type: 'sse'; name: string; url: string; auth?: MCPAuth; headers?: Record<string, string> }
  | { type: 'cloud'; name: string; identifier?: string; [key: string]: unknown };

interface MCPAuth {
  type: 'none' | 'bearer' | 'oauth2';
  token?: string;
  accessToken?: string;
}
```

### MCP Discovery

Implementations MUST:

1. Load persisted MCP server config.
2. Establish a client/session for the configured transport.
3. Call `listTools`.
4. Convert MCP tools to manifest APIs:
   - `name` maps to API name.
   - `description` maps to API description.
   - `inputSchema` maps to JSON parameters.
5. Store original connection config in `manifest.mcpParams`.
6. Mark manifest `type` as `mcp`.

### MCP Invocation

Implementations MUST:

1. Resolve the model tool call to `ChatToolPayload`.
2. Load `mcpParams` from `toolManifestMap[payload.identifier]`.
3. Parse `payload.arguments` as JSON.
4. Call MCP server tool by `payload.apiName`.
5. Convert MCP content blocks to string content.
6. Preserve raw content blocks in tool result state when possible.
7. Return a normal tool result message to the runtime.

MCP errors MUST be normalized into a failed tool result unless the MCP protocol marks the result as a successful tool-level error payload.

## Builtin Skills Contract

Builtin skills are exposed through the builtin tool identifier:

```text
lobe-skills
```

Required APIs:

```ts
type SkillsApiName = 'activateSkill' | 'readReference' | 'runCommand' | 'execScript' | 'exportFile';
```

### activateSkill

Input:

```ts
{
  name: string;
}
```

Behavior:

- Find builtin skill by exact `name`.
- If not found, find user/market skill by exact `name`.
- Return skill content.
- If the skill has resources, append a resource tree to the returned content.
- Return state with skill id/name/description/resource availability.

### readReference

Input:

```ts
{
  id: string;
  path: string;
}
```

Behavior:

- Reject paths containing `..`.
- Resolve builtin resource first.
- Fall back to installed skill resource lookup.
- Return content and metadata: encoding, file type, path, size, and optional full path.

### runCommand

Input:

```ts
{ command: string; description?: string }
```

Behavior:

- Requires human intervention by default.
- Execute in the configured skill runtime environment.
- Return stdout/stderr/exit code formatted as command output.

### execScript

Input:

```ts
{
  command: string;
  description: string;
  activatedSkills?: Array<{ id: string; name: string; description?: string }>;
}
```

Behavior:

- Requires human intervention by default.
- Prefer sandbox/cloud-aware `execScript` service when available.
- Fall back to `runCommand` when `execScript` is unavailable.
- Return stdout/stderr/exit code formatted as command output.

### exportFile

Input:

```ts
{
  path: string;
  filename: string;
}
```

Behavior:

- Export a generated file from the skill runtime environment.
- Return file id, filename, MIME type, size, and URL when available.

## Skill Context Contract

```ts
interface SkillMeta {
  identifier: string;
  name: string;
  description: string;
  location?: string;
  activated?: boolean;
  content?: string;
}

interface OperationSkillSet {
  enabledPluginIds: string[];
  skills: SkillMeta[];
}

interface ActivatedStepSkill {
  identifier: string;
  content?: string;
  activatedAtStep: number;
}
```

Rules:

- Operation-level skill set is immutable after operation creation.
- Skills whose identifier appears in `enabledPluginIds` are activated by agent configuration.
- Step-level activations override skill content for the current and subsequent steps.
- Activated skills inject full content into system context.
- Non-activated available skills inject only name/identifier/description/location.

## Context Assembly Contract

Before every `call_llm`, implementations MUST assemble model context through a deterministic pipeline.

Minimum Level 0 order:

1. Start with persisted message history.
2. Inject system role.
3. Inject system date/time and timezone.
4. Inject enabled tool system roles.
5. Inject selected and activated skills.
6. Inject selected tool and skill summaries into first user context where applicable.
7. Normalize tool-call messages for the selected model/provider.
8. Apply history truncation based on model context window.

Level 1 SHOULD also include memory, files, knowledge, topic references, credentials, agent documents, page/editor context, and variable substitution.

## Stream Event Contract

Stream events MUST be append-only and resumable by event id.

```ts
interface StreamEvent {
  id?: string;
  operationId: string;
  stepIndex: number;
  timestamp: number;
  type:
    | 'agent_runtime_init'
    | 'agent_runtime_end'
    | 'stream_start'
    | 'stream_chunk'
    | 'stream_end'
    | 'stream_retry'
    | 'tool_start'
    | 'tool_end'
    | 'step_start'
    | 'step_complete'
    | 'error';
  data: unknown;
}
```

### Stream Chunk Data

```ts
interface StreamChunkData {
  chunkType:
    | 'text'
    | 'reasoning'
    | 'tools_calling'
    | 'image'
    | 'grounding'
    | 'base64_image'
    | 'content_part'
    | 'reasoning_part';
  content?: string;
  reasoning?: string;
  toolsCalling?: ChatToolPayload[];
  grounding?: unknown;
  images?: unknown[];
  imageList?: unknown[];
  contentParts?: Array<{ type: 'text'; text: string } | { type: 'image'; image: string }>;
  reasoningParts?: Array<{ type: 'text'; text: string } | { type: 'image'; image: string }>;
}
```

Rules:

- `agent_runtime_init` uses `stepIndex = 0`.
- `agent_runtime_end` MUST include final state, reason, and reason detail.
- Text, reasoning, image, grounding, and tool-call chunks MUST be normalized by the model runtime adapter.
- A stream history store SHOULD retain at least the last 1000 events or equivalent operational window.

## Runtime Event Contract

Runtime-level events emitted by instruction executors:

```ts
type AgentEvent =
  | { type: 'init' }
  | { type: 'llm_start'; payload: unknown }
  | { type: 'llm_stream'; chunk: unknown }
  | { type: 'llm_result'; result: unknown }
  | { type: 'tool_pending'; toolCalls: ToolsCalling[] }
  | { type: 'tool_result'; id: string; result: unknown }
  | { type: 'human_approve_required'; operationId: string; pendingToolsCalling: ChatToolPayload[] }
  | {
      type: 'human_prompt_required';
      operationId: string;
      prompt: string;
      metadata?: Record<string, unknown>;
    }
  | {
      type: 'human_select_required';
      operationId: string;
      prompt?: string;
      options: Array<{ label: string; value: string }>;
      multi?: boolean;
      metadata?: Record<string, unknown>;
    }
  | { type: 'done'; reason: FinishReason; reasonDetail?: string; finalState: AgentState }
  | { type: 'error'; error: unknown }
  | {
      type: 'interrupted';
      reason: string;
      interruptedAt: string;
      canResume: boolean;
      interruptedInstruction?: unknown;
      metadata?: Record<string, unknown>;
    }
  | {
      type: 'resumed';
      reason: string;
      resumedAt: string;
      resumedFromStep: number;
      metadata?: Record<string, unknown>;
    }
  | { type: 'compression_complete'; groupId: string; parentMessageId?: string }
  | { type: 'compression_error'; error: unknown };
```

## Finish Reasons

```ts
type FinishReason =
  | 'completed'
  | 'user_requested'
  | 'user_aborted'
  | 'max_steps_exceeded'
  | 'max_steps_completed'
  | 'cost_limit_exceeded'
  | 'timeout'
  | 'agent_decision'
  | 'queued_message_interrupt'
  | 'error_recovery'
  | 'system_shutdown';
```

## Human Intervention Contract

Implementations MUST support three intervention forms:

- approval for pending tool calls
- free-form human prompt response
- single or multi-select response

Rules:

- Tools marked with required human intervention MUST pause before execution.
- Security blacklist policies MUST override user auto-run settings.
- While waiting, state status MUST be `waiting_for_human`.
- Resuming approval MUST either execute existing pending tool calls or mark them aborted.
- When `skipCreateToolMessage` is set, resumed tool execution MUST update the existing tool message instead of creating a duplicate.

## Persistence Contract

Level 1 implementations MUST persist or reconstruct:

- operation state by `operationId`
- stream events by `operationId`
- model/provider config
- tool manifests, schemas, source maps, and executor maps
- MCP server configs and discovered MCP tools
- skill registry and installed skills
- per-agent enabled tools and skills
- activated step tools and skills

Persistent stores MAY use SQL, document storage, object storage, Redis, or equivalent systems if the JSON contract is preserved.

## Error Contract

Errors SHOULD be normalized as:

```ts
interface NormalizedRuntimeError {
  kind?: string;
  code?: string;
  message: string;
  name?: string;
  body?: unknown;
}
```

Rules:

- Provider errors are normalized by model runtime adapters.
- Tool errors are returned as failed tool results when possible.
- Runtime fatal errors set state status to `error`, persist `state.error`, and emit both `error` and `agent_runtime_end`.
- MCP initialization errors SHOULD preserve stderr/detail fields when available.

## Level 0 Demo Flow

1. User selects `{ provider, model }`.
2. Runtime creates `AgentState` with `modelRuntimeConfig`.
3. Runtime resolves builtin skills manifest and selected MCP manifests into `OperationToolSet`.
4. User sends prompt.
5. Agent returns `call_llm`.
6. Context pipeline injects system role, date, tools, and skill metadata.
7. Model emits text and/or tool calls.
8. Runtime resolves tool calls with `ToolNameResolver`.
9. Runtime pauses for human approval when policy requires it.
10. Runtime executes builtin skill or MCP tool.
11. Tool result is appended as a normal tool message.
12. Agent calls LLM again.
13. Runtime finishes when no tool calls remain or the agent returns `finish`.

## Graph Agent Contract

Graph agents are declarative control-flow wrappers around the general agent runtime. A graph implementation MUST preserve normal runtime state, tool routing, model selection, and stream events while adding graph state under `AgentState.metadata.__graphContext`.

### Graph Definition

```ts
interface ReasoningGraph {
  name: string;
  description?: string;
  entry: string;
  terminal: string;
  maxBacktracks: number;
  states: Record<string, StateNode>;
  transitions: Transition[];
}

interface StateNode {
  type: 'agent' | 'llm';
  prompt: string;
  outputSchema: Record<string, unknown>;
}

interface Transition {
  from: string;
  to: string;
  condition: string;
}
```

Rules:

- `entry` and `terminal` MUST reference keys in `states`.
- `transitions` are evaluated in declaration order. First truthy transition wins.
- If no transition matches, the graph advances to the next state in declaration order.
- `condition` receives the current node structured output as `output`.
- User-authored graphs MUST use a safe expression evaluator. They MUST NOT execute arbitrary host-language code.
- `maxBacktracks` limits transitions to already visited nodes. When the limit is reached, backtracking transitions MUST be skipped.

### Graph Runtime Context

```ts
interface GraphContext {
  currentNode: string;
  nodeActive: boolean;
  extracting?: boolean;
  input: string;
  store: Record<string, Record<string, unknown>>;
  visitCount: Record<string, number>;
  backtrackCount: number;
}
```

Rules:

- Store this object at `AgentState.metadata.__graphContext`.
- `input` is initialized from the latest user message content.
- `store[stateId]` contains the structured output extracted from that state.
- `nodeActive = true` means execution is inside a node-level runtime loop.
- `extracting = true` means an `agent` node has finished its tool loop and is running a tools-disabled structured extraction call.

### Node Execution

`agent` node:

- Render the node prompt.
- Append a user message containing the rendered prompt.
- Call the general chat agent with normal tools enabled.
- When the inner agent finishes, run an extra `call_llm` with tools disabled to extract output matching `outputSchema`.
- Store extracted output in `GraphContext.store[currentNode]`.

`llm` node:

- Render the node prompt.
- Append schema instructions for `outputSchema`.
- Run exactly one `call_llm` with tools disabled.
- Store parsed JSON output in `GraphContext.store[currentNode]`.

Output parsing:

- Prefer raw JSON.
- If content contains a markdown code fence, parse the fenced body.
- If parsing fails, store `{ "_raw": content }`.

Prompt variables:

```text
{{input.question}}
{{stateId.field}}
```

Rules:

- `{{input.question}}` resolves to `GraphContext.input`.
- `{{stateId.field}}` resolves to `GraphContext.store[stateId][field]`.
- Missing values SHOULD render as explicit missing-data placeholders, not empty strings.

### Graph Finish

The graph finishes only when the terminal node completes. The runtime SHOULD return:

```ts
{
  type: 'finish',
  reason: 'completed',
  reasonDetail: `Graph "${graph.name}" completed at terminal node "${terminal}"`
}
```

## Group Orchestration Contract

Group orchestration is a supervisor/executor loop. The supervisor is stateless decision logic. Executors perform agent calls, broadcasts, delegation, and async task execution.

### Supervisor Instruction

```ts
type SupervisorInstruction =
  | {
      type: 'call_supervisor';
      payload: { supervisorAgentId: string; groupId?: string; round: number };
    }
  | { type: 'call_agent'; payload: { agentId: string; instruction?: string } }
  | {
      type: 'parallel_call_agents';
      payload: {
        agentIds: string[];
        instruction?: string;
        disableTools?: boolean;
        toolMessageId: string;
      };
    }
  | {
      type: 'exec_async_task';
      payload: {
        agentId: string;
        instruction: string;
        title?: string;
        timeout?: number;
        toolMessageId: string;
      };
    }
  | {
      type: 'exec_client_async_task';
      payload: {
        agentId: string;
        instruction: string;
        title?: string;
        timeout?: number;
        toolMessageId: string;
      };
    }
  | {
      type: 'batch_exec_async_tasks';
      payload: {
        tasks: Array<{ agentId: string; instruction: string; title?: string; timeout?: number }>;
        toolMessageId: string;
      };
    }
  | { type: 'delegate'; payload: { agentId: string; reason?: string } }
  | { type: 'finish'; reason: string };
```

### Executor Result

```ts
type ExecutorResult =
  | { type: 'init'; payload: { groupId?: string } }
  | {
      type: 'supervisor_decided';
      payload: {
        decision: GroupDecision;
        params: Record<string, unknown>;
        skipCallSupervisor?: boolean;
      };
    }
  | { type: 'agent_spoke'; payload: { agentId: string; completed: boolean } }
  | { type: 'agents_broadcasted'; payload: { agentIds: string[]; completed: boolean } }
  | {
      type: 'task_completed';
      payload: { agentId: string; success: boolean; result?: string; error?: string };
    }
  | {
      type: 'tasks_completed';
      payload: {
        results: Array<{ agentId: string; success: boolean; result?: string; error?: string }>;
      };
    }
  | { type: 'delegated'; payload: { agentId: string; completed: boolean } };

type GroupDecision =
  | 'speak'
  | 'broadcast'
  | 'delegate'
  | 'execute_task'
  | 'execute_tasks'
  | 'finish';
```

### Runtime Loop

```ts
interface GroupOrchestrationExecutorOutput {
  events: GroupOrchestrationEvent[];
  newState: AgentState;
  result?: ExecutorResult;
}

interface IGroupOrchestrationSupervisor {
  decide(result: ExecutorResult, state: AgentState): Promise<SupervisorInstruction>;
}
```

Rules:

- Start with `ExecutorResultInit`.
- Supervisor decisions SHOULD be represented as `supervisor_decided`.
- If `skipCallSupervisor` is true, the runtime MUST execute the selected action and then finish or return control according to the action result, without another supervisor call.
- `parallel_call_agents` MUST preserve the order of requested `agentIds` in output metadata.
- `disableTools = true` MUST strip tools from broadcast agent calls.
- `exec_client_async_task` is desktop/local only. Non-desktop runtimes MUST either reject it as unsupported or route to server execution only when the task does not require local capabilities.
- `delegate` transfers subsequent control to the delegated agent until it completes or hands back to the supervisor.
- The group loop MUST enforce a max round limit and emit `max_rounds_exceeded` if exceeded.

### Group Events

```ts
type GroupOrchestrationEvent =
  | { type: 'supervisor_finished' }
  | { type: 'agent_spoke'; agentId: string }
  | { type: 'agents_broadcasted'; agentIds: string[] }
  | { type: 'max_rounds_exceeded' }
  | { type: 'done'; reason: string };
```

Rules:

- Group events MUST be included in runtime traces.
- Each child agent call SHOULD carry parent operation/thread metadata for reconstruction.
- Group messages SHOULD identify the speaking agent and group id in message metadata.

## Memory Contract

Memory is durable user-scoped state consumed through two runtime surfaces:

- context injection before LLM calls
- builtin memory tools during agent execution

Background extraction and persona generation are Level 2 but SHOULD use the same memory records.

### Memory Layers

```ts
type MemoryLayer = 'activity' | 'context' | 'experience' | 'identity' | 'preference';

type MemorySourceType = 'chat_topic' | 'benchmark_locomo';
```

### Base Memory Record

```ts
interface UserMemory {
  id: string;
  userId: string | null;
  title: string | null;
  summary: string | null;
  details: string | null;
  memoryCategory: string | null;
  memoryLayer: string | null;
  memoryType: string | null;
  status: string | null;
  tags: string[] | null;
  metadata: Record<string, unknown> | null;
  accessedCount: number | null;
  accessedAt: string;
  lastAccessedAt: string;
  capturedAt: string;
  createdAt: string;
  updatedAt: string;
}
```

Rules:

- Vector fields are storage-specific and SHOULD NOT be required in runtime payloads.
- Every layer-specific record MUST reference a base memory id.
- Memory retrieval MUST enforce user isolation.
- Search results SHOULD exclude embedding vectors.
- Access metadata SHOULD be updated when memories are retrieved or injected.

### Search Memory Params

```ts
interface SearchMemoryParams {
  queries?: string[];
  layers?: MemoryLayer[];
  categories?: string[];
  tags?: string[];
  labels?: string[];
  relationships?: string[];
  status?: string[];
  types?: string[];
  effort?: 'low' | 'medium' | 'high';
  topK?: {
    activities?: number;
    contexts?: number;
    experiences?: number;
    identities?: number;
    preferences?: number;
  };
  timeIntent?: SearchMemoryTimeIntent;
  timeRange?: {
    field?: 'capturedAt' | 'createdAt' | 'endsAt' | 'episodicDate' | 'startsAt' | 'updatedAt';
    start?: string;
    end?: string;
  };
}
```

Rules:

- `queries` SHOULD drive semantic and keyword search.
- Filters MUST be conjunctive unless an implementation explicitly records another strategy in result metadata.
- `timeIntent` MUST be resolved to exact date bounds before querying.
- `effort` controls breadth/depth of retrieval, ranking, and context construction.

### Search Memory Result

```ts
interface SearchMemoryResult {
  activities: unknown[];
  contexts: unknown[];
  experiences: unknown[];
  identities?: unknown[];
  preferences: unknown[];
  meta?: {
    appliedFilters: Omit<SearchMemoryParams, 'effort' | 'topK'>;
    appliedQueries: string[];
    layers: Record<
      'activities' | 'contexts' | 'experiences' | 'identities' | 'preferences',
      {
        returned: number;
        total: number;
        hasMore: boolean;
      }
    >;
    ranking?: unknown;
  };
}
```

### Builtin Memory Tool

Builtin memory tools use identifier:

```text
lobe-user-memory
```

Required APIs:

```ts
type MemoryApiName =
  | 'searchUserMemory'
  | 'queryTaxonomyOptions'
  | 'addActivityMemory'
  | 'addContextMemory'
  | 'addExperienceMemory'
  | 'addIdentityMemory'
  | 'addPreferenceMemory'
  | 'updateIdentityMemory'
  | 'removeIdentityMemory';
```

Rules:

- `searchUserMemory` returns `SearchMemoryResult`.
- Add/update/remove tools MUST return a success flag, human-readable message, and affected ids.
- Identity update/remove SHOULD require human intervention unless an agent is explicitly trusted.
- Write tools MUST create or update the base memory record and the layer-specific record transactionally.
- `queryTaxonomyOptions` returns current category/tag/label/status/type vocabularies and SHOULD be used before extraction or constrained search.

### Context Injection

Before LLM calls, memory injection SHOULD:

1. Build a retrieval query from recent user messages, topic summary, or explicit user query.
2. Retrieve relevant memories by layer.
3. Inject a compact, attributed memory context into system or first-user context.
4. Record injected memory ids in context metadata or trace step metadata.

Rules:

- Injected memory content MUST be bounded by model context budget.
- Persona, identity, and preference memories SHOULD be prioritized for personalization.
- Activity, context, and experience memories SHOULD be prioritized when they match the current task or time range.

### Extraction Contract

Background extraction SHOULD use this job shape:

```ts
interface MemoryExtractionJob {
  userId: string;
  source: MemorySourceType;
  sourceId: string;
  sourceUpdatedAt?: string;
  layers?: MemoryLayer[];
  force?: boolean;
}
```

Extraction output:

```ts
interface MemoryExtractionResult {
  decision: Record<MemoryLayer, { shouldExtract: boolean; reasoning: string }>;
  layers: MemoryLayer[];
  processedCounts: number;
  processedLayersCount: Record<MemoryLayer, number>;
  processedErrorsCount: Record<MemoryLayer, number>;
  outputs: Partial<Record<MemoryLayer, { data?: unknown; error?: unknown }>>;
  inputs: {
    retrievedContexts?: string[];
    retrievedIdentitiesContext?: string;
  };
}
```

Rules:

- Gatekeeper decides which layers to extract.
- Layer extraction MUST tolerate partial failure.
- Recording MUST report created memory ids and per-layer counts.
- Source metadata SHOULD store status, last processed message/source marker, version, and error.

## Tracing Contract

Tracing records execution snapshots for debugging, replay, and inspection. Tracing MUST NOT be required for runtime correctness, but a Level 1 implementation SHOULD support partial and finalized snapshots.

### Execution Snapshot

```ts
interface ExecutionSnapshot {
  traceId: string;
  operationId: string;
  userId?: string;
  agentId?: string;
  topicId?: string;
  provider?: string;
  model?: string;
  startedAt: number;
  completedAt?: number;
  completionReason?:
    | 'done'
    | 'error'
    | 'interrupted'
    | 'max_steps'
    | 'cost_limit'
    | 'waiting_for_human';
  error?: { type: string; message: string };
  totalSteps: number;
  totalTokens: number;
  totalCost: number;
  externalRetryCount?: number;
  retryDelayExpression?: string;
  steps: StepSnapshot[];
}
```

### Step Snapshot

```ts
interface StepSnapshot {
  stepIndex: number;
  stepType: 'call_llm' | 'call_tool' | string;
  startedAt: number;
  completedAt: number;
  executionTimeMs: number;
  context?: {
    phase: string;
    payload?: unknown;
    stepContext?: unknown;
  };
  events?: Array<{ type: string; [key: string]: unknown }>;
  content?: string;
  reasoning?: string;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens: number;
  totalCost: number;
  messagesBaseline?: unknown[];
  messagesDelta?: unknown[];
  isCompressionReset?: boolean;
  toolsetBaseline?: unknown;
  activatedStepToolsDelta?: unknown[];
  toolsCalling?: Array<{
    identifier: string;
    apiName: string;
    arguments?: string;
  }>;
  toolsResult?: Array<{
    identifier: string;
    apiName: string;
    output?: string;
    isSuccess?: boolean;
  }>;
  externalRetryCount?: number;
}
```

Rules:

- `traceId` SHOULD equal `operationId` unless the host application needs a separate trace namespace.
- `steps` MUST be sorted by `stepIndex` in finalized snapshots.
- Step `0` SHOULD include `messagesBaseline` and `toolsetBaseline`.
- Later steps SHOULD store `messagesDelta` instead of full message history.
- Compression steps MUST set `isCompressionReset = true` and write a new `messagesBaseline`.
- Tool discovery or dynamic activation MUST record `activatedStepToolsDelta`.
- Errors and interrupted states MUST be captured in both the relevant step and final snapshot.
- Secrets, tokens, API keys, and environment variables MUST be redacted before snapshot persistence.

### Snapshot Store

```ts
interface SnapshotStore {
  get(traceId: string): Promise<ExecutionSnapshot | null>;
  getLatest(): Promise<ExecutionSnapshot | null>;
  list(options?: { limit?: number }): Promise<SnapshotSummary[]>;
  save(snapshot: ExecutionSnapshot): Promise<void>;
  savePartial(operationId: string, partial: Partial<ExecutionSnapshot>): Promise<void>;
  loadPartial(operationId: string): Promise<Partial<ExecutionSnapshot> | null>;
  listPartials(): Promise<string[]>;
  removePartial(operationId: string): Promise<void>;
}

interface SnapshotSummary {
  traceId: string;
  operationId: string;
  createdAt: number;
  durationMs: number;
  totalSteps: number;
  totalTokens: number;
  model?: string;
  completionReason?: string;
  hasError: boolean;
}
```

Rules:

- Partial snapshots SHOULD be appended after every completed step.
- Final snapshots MUST be written when an operation reaches a terminal state.
- After successful finalization, partial snapshots SHOULD be removed.
- Snapshot storage MAY be file, object, document, or relational storage if retrieval by `traceId` and `operationId` is supported.

## Conformance Fixtures

Cross-language implementations SHOULD pass fixtures for:

### Fixture A: Model Selection

Input:

```json
{
  "messages": [{ "role": "user", "content": "hello" }],
  "model": "gpt-4.1",
  "provider": "openai"
}
```

Expected:

- model runtime receives provider `openai`
- model runtime receives model `gpt-4.1`
- no provider-specific fields appear in core runtime state

### Fixture B: Builtin Skill Activation

Input tool call:

```json
{
  "apiName": "activateSkill",
  "arguments": "{\"name\":\"typescript\"}",
  "identifier": "lobe-skills",
  "type": "builtin"
}
```

Expected:

- skill content returned as tool result content
- activated skill state includes `name`, `id` or `identifier`, and `hasResources`
- next LLM context includes activated skill content

### Fixture C: MCP Tool Call

Input:

```json
{
  "manifest": {
    "identifier": "filesystem",
    "type": "mcp",
    "mcpParams": {
      "type": "stdio",
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    }
  },
  "toolCall": {
    "identifier": "filesystem",
    "apiName": "list_directory",
    "arguments": "{\"path\":\".\"}",
    "type": "mcp"
  }
}
```

Expected:

- runtime calls MCP tool `list_directory`
- MCP result content blocks are converted to string content
- raw blocks are preserved in result state when available
- result is appended as a normal tool message

### Fixture D: Human Approval

Input:

```json
{
  "toolCall": {
    "identifier": "lobe-skills",
    "apiName": "runCommand",
    "arguments": "{\"command\":\"pwd\"}",
    "type": "builtin"
  }
}
```

Expected:

- runtime sets status to `waiting_for_human`
- runtime stores pending tool call
- stream emits human approval requirement
- approval resumes execution without duplicating tool messages

### Fixture E: Graph Agent

Input:

```json
{
  "graph": {
    "name": "two-step",
    "entry": "research",
    "terminal": "final",
    "maxBacktracks": 0,
    "states": {
      "research": {
        "type": "agent",
        "prompt": "Research {{input.question}}",
        "outputSchema": { "type": "object", "properties": { "confidence": { "type": "number" } } }
      },
      "final": {
        "type": "llm",
        "prompt": "Summarize confidence {{research.confidence}}",
        "outputSchema": { "type": "object", "properties": { "answer": { "type": "string" } } }
      }
    },
    "transitions": [{ "from": "research", "to": "final", "condition": "output.confidence >= 0" }]
  },
  "userMessage": "Can this be replicated?"
}
```

Expected:

- graph context is stored at `metadata.__graphContext`
- `research` runs as an agent node with tools enabled
- `research:extract` runs with tools disabled
- `final` runs with tools disabled
- final state includes structured outputs for both nodes

### Fixture F: Group Orchestration

Input:

```json
{
  "initialResult": { "type": "init", "payload": { "groupId": "group-1" } },
  "supervisorDecision": {
    "type": "supervisor_decided",
    "payload": {
      "decision": "broadcast",
      "params": { "agentIds": ["agent-a", "agent-b"], "instruction": "Compare options" }
    }
  }
}
```

Expected:

- runtime emits a `parallel_call_agents` instruction
- child calls preserve requested agent order
- result is `agents_broadcasted`
- trace includes `agents_broadcasted` group event

### Fixture G: Memory Search And Injection

Input:

```json
{
  "search": {
    "queries": ["preferred coding style"],
    "layers": ["preference", "identity"],
    "effort": "medium",
    "topK": { "preferences": 3, "identities": 2 }
  }
}
```

Expected:

- search enforces user isolation
- result excludes embedding vectors
- result metadata includes applied queries and layer counts
- injected context records memory ids in trace or context metadata

### Fixture H: Trace Snapshot

Input:

```json
{
  "operationId": "op-1",
  "steps": [
    { "stepIndex": 0, "stepType": "call_llm" },
    { "stepIndex": 1, "stepType": "call_tool" }
  ]
}
```

Expected:

- partial snapshot is saved after each completed step
- finalized snapshot has `traceId`, `operationId`, sorted steps, totals, and completion reason
- step 0 includes `messagesBaseline` and `toolsetBaseline`
- step 1 includes `messagesDelta` and tool result metadata
- secrets are redacted before persistence

## Open Decisions

The following details are implementation-specific until promoted into this contract:

- exact database schema names and migration strategy
- exact context compression summary format
- exact graph-agent transition expression language
- exact cloud sandbox protocol
- exact market installation protocol for remote skills and MCPs
