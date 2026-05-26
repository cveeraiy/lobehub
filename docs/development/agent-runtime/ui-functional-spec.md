# Core Agent UI Functional Specification

## Purpose

This document defines the user interface requirements for the core agent features. It is based on the existing repository structure and product surfaces, but it is written generically so the UI can be ported to a React application without depending on Next.js, Zustand, antd, or LobeHub-specific component libraries.

Related backend/runtime specs:

- [System Functional Specification](./sfs.md)
- [Portable Design](./design.md)
- [Implementation Contract](./implementation-contract.md)
- [API Contract](./api-contract.md)
- [Runtime Event Protocol](./runtime-event-protocol.md)
- [Provider Adapter Specification](./provider-adapter-spec.md)
- [Persistence And DDL Specification](./persistence-ddl-spec.md)
- [Conformance Test Plan](./conformance-test-plan.md)

## Scope

The UI shall support:

- Chat with single agents
- Group agent chat
- Agent profile and settings
- Model/provider selection
- Tool, MCP, and skill enablement
- Memory enablement, memory browsing, and memory extraction
- Human intervention and tool approval
- Tool call rendering
- Task management and task execution
- Knowledge/file resource management
- Runtime status, streaming, errors, reconnect, and trace-oriented inspection
- Agent Signal-visible outcomes where surfaced in UI

This spec covers functional behavior, data contracts, and interaction states. It does not prescribe styling, routing library, component library, or exact visual design.

## UI Architecture Principles

### React Portability

The UI should be decomposed into:

- Route-level pages
- Feature-level containers
- Pure presentational components
- View models/selectors
- Service adapters
- Local component state for transient UI only

React-portable assumptions:

- Routing can be React Router, Next.js router, TanStack Router, or any equivalent.
- Data fetching can be SWR, React Query, Apollo, custom hooks, or service calls.
- State can be Zustand, Redux, Jotai, React context, or local reducer stores.
- Component library can be any design system.

### Separation Of Concerns

| Layer                    | UI responsibility                                                 |
| ------------------------ | ----------------------------------------------------------------- |
| Page                     | Route params, layout composition, major loading/error boundaries. |
| Feature container        | Fetch data, bind actions, compute view model.                     |
| Presentational component | Render props, emit UI events, no direct API calls.                |
| Store/view model         | Normalize entity state and expose selectors.                      |
| Service adapter          | Backend API, websocket/gateway, upload, local desktop bridge.     |

### Required UI States

Every async surface shall handle:

- initial loading
- empty state
- loaded state
- incremental updating state
- optimistic update state where used
- validation errors
- network/API errors
- permission or unavailable-platform state
- stale/reconnect state

## Core Navigation Model

The product should expose these primary areas:

| Area                   | Purpose                                                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Home / Agent list      | Browse, search, pin, group, create, duplicate, and delete agents or agent groups.                                           |
| Agent chat             | Conversation with one agent.                                                                                                |
| Group chat             | Conversation with multiple agents and supervisor/orchestrator.                                                              |
| Agent profile/settings | Configure metadata, model, prompt, chat behavior, tools, skills, documents, memory, opening messages, and TTS if supported. |
| Community/store        | Browse installable agents, groups, MCPs, and skills.                                                                        |
| MCP manager            | Install, configure, inspect, and remove MCP servers/tools.                                                                  |
| Skill store/editor     | Browse, install, edit, upload, and inspect skills.                                                                          |
| Memory                 | Browse and manage persona/identity/context/experience/preference/activity memories.                                         |
| Resources/knowledge    | Manage files, documents, knowledge bases, chunks, previews, and assignments.                                                |
| Tasks                  | Create, run, pause, schedule, review, and inspect agent tasks.                                                              |
| Provider/settings      | Configure providers, models, keys, fetch mode, default models, and runtime settings.                                        |

## Application Shell

### Requirements

The shell shall provide:

- responsive layout for desktop and mobile
- sidebar or navigation rail for major areas
- route-aware active state
- global search or command menu where supported
- user/account/settings access
- runtime connection indicators where relevant
- toast/notification host
- modal host
- portal/drawer host for thread or task panels

### Responsive Behavior

- Desktop: persistent sidebar plus main content.
- Tablet/mobile: collapsible navigation, drawers for settings/detail panels, bottom or compact action bars.
- Chat input must stay reachable while messages scroll.

## Agent List And Home

### Functional Requirements

The home UI shall allow users to:

- view pinned agents and groups
- view grouped and ungrouped agents
- create an agent
- create a group agent
- duplicate agents/groups
- rename agents/groups
- pin/unpin agents/groups
- move agents between sidebar groups
- sort groups
- delete agents/groups with confirmation
- start a new chat from a prompt
- send a prompt directly as a new agent or group conversation where supported

### Entity Card/List Item

Each agent item should show:

- avatar or generated visual
- title
- short description
- provider/model hint where useful
- pinned/group status
- active/running indicator if an operation is active
- context menu actions

Each group item should show:

- group avatar composed from members
- group title
- member count
- supervisor/orchestrator hint where useful
- context menu actions

## Agent Chat UI

### Main Layout

The agent chat page shall contain:

- page title/header with agent identity and actions
- conversation message list
- optional thread/portal panel
- chat input
- action bar for model/search/memory/tools/knowledge/history/params
- runtime status area

### Conversation Context

The page shall hold a conversation context object:

```ts
interface ConversationContext {
  agentId?: string;
  groupId?: string;
  topicId?: string;
  threadId?: string;
  taskId?: string;
  scope?: string;
  isSharePage?: boolean;
}
```

The UI must pass this context to chat actions, message list fetches, memory prefetch, notebook/resource prefetch, and gateway reconnect logic.

### Message List

Message list shall render:

- user messages
- assistant messages
- assistant group messages
- supervisor/group messages
- tool messages
- task messages
- compressed history groups
- context injection summaries where exposed
- thinking/reasoning indicators
- errors
- follow-up suggestions
- reactions/actions

### Message Ordering And Trees

The UI should support:

- chronological message order
- parent/child relationship for tool messages and thread replies
- grouped assistant parts where streaming emits multiple parts
- collapsed compressed history groups
- task or tool message nesting when appropriate

### Streaming Behavior

While a response streams:

- show assistant message shell immediately
- append streamed content incrementally
- show thinking/reasoning separately if supported
- show tool-call pending placeholders when tool calls appear
- keep scroll anchored unless user has manually scrolled away
- expose stop/abort action
- preserve partially streamed content on error

### Runtime Status

The chat UI shall represent:

- idle
- sending
- streaming
- tool executing
- waiting for human
- reconnecting
- interrupted
- completed
- errored

## Chat Input

### Required Capabilities

The input shall support:

- rich text or plain text message entry
- file attachment
- image/video attachment where supported
- mention agents
- mention tools/skills where supported
- reference existing topics
- prompt transform
- speech-to-text where supported
- send
- stop generation
- clear input
- token count display
- selected context chips

### Action Bar

The chat input action bar shall expose controls for:

- model selection
- model parameters
- search/web browsing
- memory enable/effort
- tools/MCP/skills
- knowledge/files
- history/context count
- agent mode
- upload
- save topic
- typography/input mode where supported

Each action control shall have:

- active/inactive state
- disabled state with reason
- loading state when data is being fetched
- compact mobile presentation
- keyboard accessibility

### Send Validation

The send button shall be disabled when:

- input is empty and no attachments/context actions exist
- required agent/topic context is missing
- upload is still processing
- runtime is already sending and queuing is not supported
- provider/model configuration is invalid

When validation fails, the UI should show actionable feedback.

## Model And Provider UI

### Provider Configuration

The provider settings UI shall allow:

- enable/disable provider
- configure API keys or key vault
- choose client-side or server-side fetch mode
- view provider logo/name/description
- set provider-specific config
- test/check model where supported
- handle missing/invalid key errors

### Model Selection

The model selector shall show:

- provider grouping
- model display name
- model type or abilities
- context window
- enabled/disabled state
- custom/builtin/remote source
- pricing or warning hints where available

Selection should update the active chat runtime config without losing unsent input.

## Agent Settings UI

### Sections

Agent settings shall include:

- metadata: title, description, tags, avatar, background
- category/group placement
- model/provider and model parameters
- system prompt
- few-shot examples where supported
- chat behavior: history count, compression, memory, tool permissions, search settings
- tools/plugins/MCP/skills
- files and knowledge bases
- agent documents
- opening message and opening questions
- TTS or voice settings where supported

### Editing Behavior

Settings may be edited in a modal, dedicated page, or side panel. The UI shall support:

- form initialization from current agent config
- dirty state
- validation
- save
- reset/cancel
- optimistic or confirmed update
- disabled fields for virtual/system agents where applicable

### Agent Documents

The agent documents UI shall show:

- document title/filename
- enabled/loading state
- access policy summary
- policy load state
- delete/disable/enable actions
- association to canonical document

## Tool UI

### Tool Picker

The tool picker shall show:

- builtin tools
- installed plugin tools
- MCP tools
- skill-provided tools
- external integration tools
- availability by platform
- enabled/disabled state
- connected/disconnected state for remote integrations
- search/filter

Each tool item shall show:

- icon/logo
- name
- description
- source type
- required setup/authorization state
- action: enable, disable, configure, install, connect, inspect

### Tool Message Rendering

Tool messages shall render:

- tool name and API name
- call status: pending, running, success, failed, cancelled, waiting approval
- arguments summary
- result summary
- expandable raw arguments/result
- custom renderer when a tool provides UI
- retry or copy actions where safe

### Tool Discovery / Activation

When runtime activates tools dynamically, the UI should show:

- newly activated tool list
- why the tool was activated if available
- step association
- allow user to inspect or disable future use

## MCP UI

### MCP List

The MCP manager shall support:

- list installed MCP servers
- list market/community MCP entries
- search/filter
- install from registry
- import from manifest/config
- remove server
- status indicators: disconnected, connecting, connected, error

### MCP Detail

The detail view shall show:

- server metadata
- deployment/transport type
- install status/progress
- tool schemas
- available APIs
- authorization/config fields
- agents using this MCP/tool
- logs or error details where available

### Install Progress

Install UI shall show:

- current step
- success/failure state
- recoverable error instructions
- retry/remove actions

## Skill UI

### Skill Store

The skill store shall support:

- builtin skills
- market/community skills
- custom/user skills
- MCP-related skills where applicable
- search/filter
- skill detail view
- install/uninstall
- upload skill package
- import from URL/GitHub

### Skill Detail

Skill detail shall show:

- name, description, author/source
- readme/introduction
- manifest/schema
- resources/files
- tools exposed by skill
- agents using this skill
- install status

### Skill Editor

Skill editor shall support:

- edit metadata
- edit content/instructions
- manage resources
- validate manifest/content
- save
- publish/export if supported

## Memory UI

### Memory Entry Points

Memory appears in:

- chat input memory toggle and effort selector
- agent settings memory configuration
- memory management page
- memory tool call renders
- memory extraction/analysis status

### Memory Management Page

Memory UI shall provide separate views for:

- home/overview
- identities
- contexts
- experiences
- preferences
- activities

Each view shall support:

- grid/list/timeline view where applicable
- filters
- tags
- date/time display
- source links
- detail panel
- edit modal
- delete/purge
- loading and empty states

### Memory Detail

Detail panel shall show layer-specific fields:

- base title/summary/details
- tags/category/type
- captured/accessed timestamps
- source links
- associated objects/subjects/locations
- vector-derived highlights where supported
- layer fields such as preference directives, activity times, experience learning, identity relationship

### Memory Analysis

The memory analysis UI shall support:

- trigger extraction for date range or selected topics
- show progress
- show pending/running/success/error status
- allow cancellation where backend supports it
- refresh memory lists after completion

## Human Intervention UI

### Approval Bar

When runtime emits `human_approve_required`, the UI shall show an intervention bar or modal with:

- tool name/API
- argument summary
- risk/reason if available
- approval actions
- reject action
- reject and continue action where supported
- optional detail expansion

The chat input should be visually disabled or contextualized while waiting for approval unless queuing is supported.

### Prompt And Select Requests

For `human_prompt_required`, UI shall show:

- prompt text
- input field
- submit/cancel

For `human_select_required`, UI shall show:

- prompt text
- option list
- single or multi select behavior
- submit/cancel

### Resume Behavior

After response:

- intervention UI closes
- runtime resumes or new resume operation starts
- pending tool message updates in place
- no duplicate tool message is created
- errors show inline and allow retry where safe

## Group Agent UI

### Group Profile

Group profile shall allow:

- edit title, description, avatar/background
- configure supervisor/orchestrator model
- manage members
- set member roles/order
- enable/disable members
- show group instructions/config

### Member Selection

Member selection modal shall support:

- create group mode
- add member mode
- select agents
- choose host/supervisor config
- preview members

### Group Conversation

Group chat shall show:

- group avatar/title
- participant/member identities
- supervisor messages
- agent council or member response grouping
- broadcast responses
- delegated agent indication
- group task messages

## Task UI

### Task List

Task UI shall support:

- list view
- kanban view
- grouped views
- create task inline
- create task modal
- filters and hidden columns
- priority/status/assignee tags
- latest activity
- subtask progress
- trigger/schedule tags

### Task Detail

Task detail shall show:

- editable title
- instruction
- properties
- model config
- schedule config
- assignee
- parent task
- subtasks
- topics/runs
- artifacts/documents
- comments/activity
- run/pause actions

### Topic Chat Drawer

Task topic drawer shall show the underlying topic conversation for a task run, including runtime status and errors.

## Knowledge And Resource UI

### Resource Manager

The resource UI shall support:

- files and folders
- knowledge libraries
- upload
- drag/drop
- preview
- file detail
- fullscreen preview
- folder path navigation
- assign files to knowledge bases
- assign knowledge bases to agents

### Knowledge In Chat

Chat input knowledge control shall allow:

- attach active files
- select knowledge bases
- show active context chips
- remove selected context
- indicate unavailable or still-indexing resources

## Runtime Operation UI

### Operation Lifecycle

The UI shall track operation state:

```ts
type RuntimeStatus =
  | 'idle'
  | 'starting'
  | 'streaming'
  | 'tool_running'
  | 'waiting_for_human'
  | 'reconnecting'
  | 'done'
  | 'error'
  | 'interrupted';
```

### Reconnect

If an operation id exists in message/topic metadata, the UI shall:

- reconnect to stream/gateway where possible
- fetch latest operation status
- continue rendering existing streamed content
- avoid sending duplicate user messages
- expose retry only after determining operation is terminal or missing

### Abort

Stop/abort UI shall:

- abort current LLM stream when possible
- resolve pending tool calls as cancelled where needed
- update assistant/tool messages
- leave conversation in a resumable or final state according to backend response

## Error UI

Errors shall be shown at the most useful location:

- provider config errors: provider/model settings callout
- chat send errors: assistant error bubble
- tool errors: tool message error state
- MCP install errors: install progress detail
- memory extraction errors: analysis status/detail
- task errors: task detail and topic card
- reconnect errors: runtime status banner

Error payloads should expose:

- user-friendly message
- provider/model if relevant
- tool identifier/API if relevant
- retry action where safe
- copy diagnostic details action

## State Model For React Port

Recommended normalized state slices:

```ts
interface AgentUISlices {
  agents: EntityState<Agent>;
  groups: EntityState<AgentGroup>;
  topics: EntityState<Topic>;
  messages: EntityState<Message>;
  operations: EntityState<RuntimeOperation>;
  tools: EntityState<ToolMeta>;
  mcpServers: EntityState<MCPServer>;
  skills: EntityState<Skill>;
  memories: {
    identities: EntityState<IdentityMemory>;
    contexts: EntityState<ContextMemory>;
    experiences: EntityState<ExperienceMemory>;
    preferences: EntityState<PreferenceMemory>;
    activities: EntityState<ActivityMemory>;
    topicCache: Record<string, RetrievedMemories>;
  };
  tasks: EntityState<Task>;
  resources: EntityState<Resource>;
  providers: EntityState<Provider>;
  models: EntityState<Model>;
}
```

UI-only state should include:

- active route context
- selected agent/group/topic
- open modals/drawers
- draft chat input
- selected files/tools/skills
- pending uploads
- expanded message/tool ids
- scroll anchor state
- current filters/sort/view modes

## Service Adapter Contracts

A React port should define service interfaces independent from components:

```ts
interface ChatService {
  sendMessage(input: SendMessageInput): Promise<SendMessageResult>;
  abortOperation(operationId: string): Promise<void>;
  reconnectOperation(operationId: string, handlers: RuntimeStreamHandlers): Unsubscribe;
  submitHumanApproval(input: HumanApprovalInput): Promise<void>;
}

interface AgentService {
  listAgents(): Promise<Agent[]>;
  getAgent(id: string): Promise<Agent>;
  createAgent(input: CreateAgentInput): Promise<Agent>;
  updateAgent(id: string, patch: Partial<Agent>): Promise<Agent>;
  deleteAgent(id: string): Promise<void>;
}

interface ToolService {
  listTools(): Promise<ToolMeta[]>;
  updateAgentTools(agentId: string, toolIds: string[]): Promise<void>;
}

interface MemoryService {
  retrieveForTopic(topicId: string): Promise<RetrievedMemories>;
  queryLayer(layer: MemoryLayer, params: QueryParams): Promise<PagedResult<MemoryItem>>;
  updateMemory(id: string, patch: Partial<MemoryItem>): Promise<void>;
  deleteMemory(id: string): Promise<void>;
  triggerExtraction(input: ExtractionInput): Promise<AsyncTaskRef>;
}
```

## Accessibility Requirements

The UI shall support:

- keyboard navigation through chat input, action bar, message actions, modals, and lists
- focus trap inside modals/drawers
- visible focus states
- ARIA labels for icon-only buttons
- screen-reader-friendly streaming status
- non-color-only status indicators
- reduced-motion mode for streaming/typing animations

## Internationalization Requirements

All user-facing text shall be externalized:

- labels
- actions
- empty states
- errors
- tool/intervention status
- memory/task status
- validation messages

Dynamic provider/tool/model names may remain data-driven.

## Porting Checklist

1. Build the shell and primary routes.
2. Implement agent/group list and routing context.
3. Implement conversation message list and chat input.
4. Add streaming runtime operation state.
5. Add tool message rendering and human intervention UI.
6. Add provider/model selector and settings.
7. Add agent settings sections.
8. Add tool picker and MCP manager.
9. Add skill store/detail/editor.
10. Add memory pages and chat memory toggle.
11. Add resource/knowledge manager.
12. Add task list/detail and topic drawer.
13. Add reconnect/abort/error flows.
14. Add accessibility, i18n, and responsive checks.

## Acceptance Criteria

A React implementation satisfies this UI spec when:

- A user can create/configure an agent and chat with it.
- A user can select provider/model and see provider errors clearly.
- A user can enable tools, MCPs, skills, memory, and knowledge for an agent.
- Tool calls render with pending/success/error states.
- Risky tool calls pause for approval and resume without duplicate messages.
- Memory can be browsed by layer and injected/toggled in chat.
- A group chat can show supervisor/member responses.
- A task can be created, run, paused, inspected, and linked to a topic conversation.
- Runtime streaming, abort, reconnect, and error states are visible and recoverable.
- The UI works on desktop and mobile layouts.
- Core state/services are decoupled enough to swap routing, state, data fetching, and design system libraries.
