# SFS: Skills System & Agent Association

**Version:** 1.0\
**Scope:** `src/store/tool/slices/agentSkills/`, `src/server/services/skill/`, `src/server/routers/lambda/agentSkills.ts`, `src/database/schemas/agentSkill.ts`, `src/store/agent/slices/plugin/`

---

## 1. Overview

The Skills system allows users to create, import, and manage reusable AI tool packages called **Skills**. A Skill packages a prompt or executable capability (via a `SKILL.md` or ZIP archive) alongside a manifest that declares its identity. Skills are independent of agents and exist in a personal skill library. An agent gains access to a skill by having its `identifier` added to the agent's `plugins` string array.

---

## 2. Core Data Types

### `SkillManifest`

Validated by `skillManifestSchema` from `@lobechat/types`.

| Field         | Type                       | Required | Description                 |
| ------------- | -------------------------- | -------- | --------------------------- |
| `name`        | `string`                   | Yes      | Human-readable name         |
| `description` | `string`                   | Yes      | What the skill does         |
| `author`      | `string \| { name, url? }` | No       | Author metadata             |
| `version`     | `string`                   | No       | Semver string               |
| `repository`  | `string` (URL)             | No       | Source repo                 |
| `sourceUrl`   | `string` (URL)             | No       | Set automatically on import |
| `license`     | `string`                   | No       | SPDX license identifier     |
| `permissions` | `string[]`                 | No       | Declared capability scope   |

### `SkillListItem`

Lightweight type used in list views and Zustand state.

| Field                     | Type                              | Description                                      |
| ------------------------- | --------------------------------- | ------------------------------------------------ |
| `id`                      | `string`                          | DB primary key (UUID)                            |
| `identifier`              | `string`                          | Stable tool identifier used in agent `plugins[]` |
| `name`                    | `string`                          | Display name                                     |
| `description`             | `string \| null`                  | Short description                                |
| `manifest`                | `SkillManifest`                   | Full manifest object                             |
| `source`                  | `'builtin' \| 'market' \| 'user'` | Origin of this skill                             |
| `zipFileHash`             | `string \| null`                  | Hash of uploaded ZIP (dedup key)                 |
| `createdAt` / `updatedAt` | `Date`                            | Timestamps                                       |

### `SkillItem`

Full type including content, returned by detail endpoints.

Extends `SkillListItem` with:

| Field        | Type                                             | Description                         |
| ------------ | ------------------------------------------------ | ----------------------------------- |
| `content`    | `string \| null`                                 | Raw skill content (Markdown / code) |
| `resources`  | `Record<VirtualPath, SkillResourceMeta> \| null` | Attached resource files             |
| `editorData` | `Record<string, any> \| null`                    | Editor UI state                     |

### `SkillResourceMeta`

| Field        | Type     | Description                          |
| ------------ | -------- | ------------------------------------ |
| `fileHash`   | `string` | S3 / storage key                     |
| `size`       | `number` | Bytes                                |
| `content`    | `string` | Inline content (builtin skills only) |
| `documentId` | `string` | Optional document reference          |

---

## 3. Database Schema

**Table:** `agent_skills`\
**File:** `src/database/schemas/agentSkill.ts`

```
agent_skills
├── id              TEXT        PK
├── name            TEXT        NOT NULL
├── description     TEXT        NOT NULL
├── identifier      TEXT        NOT NULL  (indexed)
├── source          TEXT        NOT NULL  ('builtin' | 'market' | 'user')
├── manifest        JSONB       NOT NULL  (SkillManifest)
├── content         TEXT
├── editor_data     JSONB
├── resources       JSONB                 (Record<VirtualPath, SkillResourceMeta>)
├── zip_file_hash   VARCHAR(64)           (FK → globalFiles, indexed)
├── user_id         TEXT        NOT NULL  (FK → users, cascade delete, indexed)
├── accessed_at     TIMESTAMP
├── created_at      TIMESTAMP
└── updated_at      TIMESTAMP

Unique index: (user_id, name)
```

**Relationships:**

- `user_id → users.id` — each skill is owned by one user; deleting a user cascades to their skills
- `zip_file_hash → globalFiles` — optional reference to the stored ZIP archive

---

## 4. Skill Creation Flows

### 4.1 Manual Creation

```
UI form (name, description, content, manifest fields)
  → agentSkillService.createSkill(CreateSkillInput)
  → TRPC: agentSkills.create
  → AgentSkillModel.create(data)
  → INSERT INTO agent_skills
  → refreshAgentSkills() updates Zustand state
```

`CreateSkillInput` carries name, description, identifier, manifest, and optionally content.

### 4.2 Import from GitHub

```
User supplies GitHub URL (repo or subdirectory)
  → agentSkillService.importFromGitHub(ImportGitHubInput)
  → TRPC: agentSkills.importFromGitHub
  → SkillImporter.importFromGitHub()
      ├── GitHub.downloadRepoZip(owner, repo, ref, basePath)
      ├── SkillParser.parseZipPackage(buffer, basePath)
      │     ├── findSkillMd() — looks at root, first-level subdir, basePath
      │     ├── parseSkillMd() — gray-matter frontmatter → SkillManifest
      │     └── extractResources() — collects non-SKILL.md files
      ├── Generate identifier from repo owner/name
      ├── Dedup check: find existing by identifier + zipHash
      │     → returns { status: 'unchanged' } if no change
      ├── Upload ZIP to S3, store resources
      └── AgentSkillModel.create() or .update()
  → Returns SkillImportResult { skill, status: 'created' | 'updated' | 'unchanged' }
  → refreshAgentSkills()
```

### 4.3 Import from URL

```
User supplies a direct URL
  → SkillImporter.importFromUrl()
      ├── If GitHub URL → delegate to importFromGitHub()
      ├── If URL ends with .zip → fetch buffer → parseZipPackage()
      └── Otherwise → fetch text → parseSkillMd()
  → Same dedup + storage + create/update logic
```

### 4.4 Import from ZIP Upload

```
User uploads a .zip file
  → agentSkillService.importFromZip(ImportZipInput)
  → SkillImporter.importFromZip()
      ├── Download ZIP to temp path
      ├── SkillParser.parseZipPackage()
      └── Store + create/update skill record
```

### 4.5 Import from Ethos Market

```
TRPC: agentSkills.importFromMarket
  → Fetches skill package from Ethos Market API
  → Same parse/store/create pipeline
  → source = 'market'
```

---

## 5. Skill Parsing (`SkillParser`)

**File:** `src/server/services/skill/parser.ts`

| Method                                   | Input               | Output                                                                          |
| ---------------------------------------- | ------------------- | ------------------------------------------------------------------------------- |
| `parseSkillMd(text)`                     | Raw SKILL.md string | `ParsedSkill { content, manifest, raw }`                                        |
| `parseZipPackage(buffer, basePath?)`     | ZIP buffer          | `ParsedZipSkill { content, manifest, resources: Map, zipHash, skillZipBuffer }` |
| `parseZipFile(path)`                     | File path           | Same as above                                                                   |
| `findSkillMd(entries, basePath?)`        | ZIP entries         | `ZipEntry` for SKILL.md                                                         |
| `extractResources(entries, skillMdPath)` | ZIP entries         | `Map<VirtualPath, Buffer>`                                                      |
| `repackSkillZip(entries)`                | ZIP entries         | Deterministic ZIP buffer (fixed mtime for stable hashing)                       |

**SKILL.md format:**

```markdown
---
name: My Skill
description: Does something useful
author: Alice
version: 1.0.0
---

Skill content (Markdown or code) goes here.
```

**Deduplication key:** SHA-256 of the repacked ZIP buffer (`zipHash`). Before inserting, the importer queries for an existing record with the same `identifier` and `zipFileHash`. If both match → `status: 'unchanged'`. If identifier matches but hash differs → update.

---

## 6. Backend API Layer

**File:** `src/server/routers/lambda/agentSkills.ts`\
All endpoints are authenticated TRPC procedures scoped to the current user.

| Procedure           | Type     | Description                                    |
| ------------------- | -------- | ---------------------------------------------- |
| `create`            | mutation | Manual skill creation                          |
| `delete`            | mutation | Delete skill by `id`                           |
| `update`            | mutation | Update metadata / content                      |
| `getById`           | query    | Fetch full `SkillItem` by DB id                |
| `getByIdentifier`   | query    | Fetch by `identifier` string                   |
| `getByName`         | query    | Fetch by display name                          |
| `getByIdWithZipUrl` | query    | Fetch `SkillItem` + presigned ZIP download URL |
| `importFromGitHub`  | mutation | Import from GitHub repo/subdir                 |
| `importFromUrl`     | mutation | Import from any URL                            |
| `importFromZip`     | mutation | Import from uploaded ZIP                       |
| `importFromMarket`  | mutation | Import from Ethos Market                       |
| `list`              | query    | List all skills (optional `source` filter)     |
| `listBySource`      | query    | Equivalent to `list` with `source` param       |
| `search`            | query    | Full-text search on name + description         |
| `listResources`     | query    | Get resource tree for a skill                  |
| `readResource`      | query    | Read single resource file content              |

---

## 7. Zustand Store (`agentSkills` slice)

**Files:** `src/store/tool/slices/agentSkills/`

### 7.1 State

```typescript
interface AgentSkillsState {
  agentSkills: SkillListItem[]; // master list, synced from server
  agentSkillDetailMap: Record<string, SkillItem>; // cache: id → full detail
  agentSkillsLoading: boolean;
}
```

### 7.2 Actions

| Action                                       | Behavior                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| `useFetchAgentSkills(enabled)`               | SWR hook — fetches list on mount; updates `agentSkills` on success        |
| `refreshAgentSkills()`                       | Imperative re-fetch; replaces `agentSkills` in state                      |
| `createAgentSkill(params)`                   | Calls service, then `refreshAgentSkills()`                                |
| `importAgentSkillFromGitHub/Url/Zip(params)` | Calls service, then `refreshAgentSkills()`                                |
| `updateAgentSkill(params)`                   | Updates `agentSkillDetailMap[id]`, invalidates SWR cache, refreshes list  |
| `deleteAgentSkill(id)`                       | Removes from `agentSkillDetailMap`, invalidates SWR cache, refreshes list |
| `fetchAgentSkillDetail(id)`                  | Returns from cache if present; otherwise fetches and caches               |
| `useFetchAgentSkillDetail(skillId)`          | SWR hook — fetches detail + resource tree in parallel                     |

### 7.3 Selectors

**File:** `src/store/tool/slices/agentSkills/selectors.ts`

| Selector                           | Returns                                               |
| ---------------------------------- | ----------------------------------------------------- |
| `getAgentSkills(s)`                | All `SkillListItem[]`                                 |
| `getUserAgentSkills(s)`            | Filtered to `source === 'user'`                       |
| `getMarketAgentSkills(s)`          | Filtered to `source === 'market'`                     |
| `getAgentSkillByIdentifier(id)(s)` | Single skill by identifier                            |
| `getAgentSkillDetail(id)(s)`       | `SkillItem` from detail cache                         |
| `isAgentSkill(identifier)(s)`      | Boolean — is this identifier a known skill            |
| `agentSkillMetaList(s)`            | `LobeToolMeta[]` — skills in unified tool meta format |

`agentSkillMetaList` maps each skill to:

```typescript
{
  author: string,          // from manifest.author
  identifier: skill.identifier,
  meta: {
    avatar: '🧩',
    description: skill.description ?? manifest.description,
    title: skill.name,
  },
  type: 'builtin'          // treated as builtin tools in the tool system
}
```

---

## 8. Agent–Skill Association

### 8.1 Data Model

The agent's `plugins` column in the `agents` table (`src/database/schemas/agent.ts:46`) is a `JSONB string[]` array of tool identifiers:

```sql
agents
└── plugins  JSONB  -- e.g. ["web-search", "code-interpreter", "my-custom-skill"]
```

Skills, plugins, and built-in tools all share the same `plugins` array — there is no separate `skills` column. The distinction is resolved at runtime by looking up the identifier across all tool sources.

### 8.2 Toggling a Skill On/Off

**File:** `src/store/agent/slices/plugin/action.ts`

```
User enables/disables a skill in agent settings
  → togglePlugin(identifier, open?)
      ├── Read current agent config (agentSelectors.currentAgentConfig)
      ├── Produce new config:
      │     if open && identifier not in plugins → push identifier
      │     if !open && identifier in plugins   → splice identifier out
      └── updateAgentConfig(newConfig)            → persist to DB
```

`removePlugin(id)` is a convenience wrapper for `togglePlugin(id, false)`.

### 8.3 Reading Active Plugins for an Agent

**File:** `src/store/agent/selectors/selectors.ts`

```typescript
currentAgentPlugins(s); // → string[] from config.plugins
displayableAgentPlugins(s); // → filterToolIds(plugins) — removes platform-unavailable tools
```

`filterToolIds` (`src/helpers/toolFilters.ts`) strips tools that cannot run in the current environment (e.g. the `LocalSystem` tool outside of desktop).

### 8.4 Runtime Tool Discovery

**File:** `src/store/tool/selectors/tool.ts`

`availableToolsForDiscovery(s)` provides the picker UI with all tools a user can add to an agent. It aggregates 4 sources and deduplicates via exclusion sets:

```
builtinSkillIds  ← s.builtinSkills[].identifier
agentSkillIds    ← s.agentSkills[].identifier
klavisIds        ← s.servers[].identifier
lobehubSkillIds  ← s.lobehubSkillServers[].identifier

Sources included:
1. s.builtinTools        — exclude builtinSkillIds, platform-unavailable
2. s.installedPlugins    — exclude klavisIds, lobehubSkillIds, agentSkillIds
3. s.servers (Klavis MCP)  — connected + has tools
4. s.lobehubSkillServers   — connected only
```

Note: **user-created agent skills are excluded from the discovery list** — they are surfaced through a dedicated skills panel, not the general tool picker.

---

## 9. End-to-End Flow: Enabling a Skill on an Agent

```
1. User opens skill library
   → useFetchAgentSkills(true) populates agentSkills[]

2. User clicks "Add to Agent"
   → toolStore.togglePlugin(skill.identifier, true)
   → agent config plugins[] += skill.identifier
   → updateAgentConfig() persists to DB

3. Agent chat session starts
   → currentAgentPlugins(s) → ["...", "my-skill-identifier"]
   → displayableAgentPlugins filters for current env
   → agent runtime resolves tool manifests for all identifiers
   → skill's SKILL.md content / manifest injected into tool context

4. LLM invokes skill
   → tool call dispatched to skill executor
   → result returned to conversation
```

---

## 10. MCP Integrations

MCP (Model Context Protocol) tool providers come in two distinct flavours in this codebase: **Klavis** (third-party MCP servers accessed via OAuth) and **Ethos Skill servers** (first-party Ethos-hosted providers). Both are stored in Zustand slices, exposed through the unified tool selector, and associated to agents via the same `agent.plugins[]` identifier mechanism as user skills.

---

### 10.1 Klavis MCP Servers

**Files:** `src/store/tool/slices/klavisStore/`

#### Core Types

| Type                 | Key Fields                                                                                              |
| -------------------- | ------------------------------------------------------------------------------------------------------- |
| `KlavisServer`       | `identifier`, `instanceId`, `isAuthenticated`, `oauthUrl`, `serverUrl`, `status`, `tools: KlavisTool[]` |
| `KlavisTool`         | `name`, `description`, `inputSchema`                                                                    |
| `KlavisServerStatus` | `CONNECTED`, `ERROR`, `PENDING_AUTH`                                                                    |

#### State (`KlavisStoreState`)

```typescript
{
  servers: KlavisServer[];              // all registered Klavis servers
  executingToolIds: Set<string>;        // tool call in-flight tracker
  loadingServerIds: Set<string>;        // servers being initialised
  isServersInit: boolean;               // first-load flag
}
```

#### Server Lifecycle

```
1. createKlavisServer(params)
   → POST /api/klavis/servers
   → isAuthenticated ? status = CONNECTED : status = PENDING_AUTH
   → oauthUrl returned for PENDING_AUTH case → open in browser

2. completeKlavisServerAuth(identifier)   [OAuth callback]
   → refreshKlavisServerTools(identifier)
       ├── Fetch tool list from Klavis API
       ├── If auth error → remove server from state
       ├── If success → status = CONNECTED, tools updated
       └── If other error → status = ERROR

3. removeKlavisServer(identifier)
   → DELETE /api/klavis/servers/:id
   → Remove from state
```

#### Status Transitions

```
createKlavisServer()
  ├── authenticated  → CONNECTED
  └── not yet        → PENDING_AUTH
          ↓
  completeKlavisServerAuth()
          ├── success → CONNECTED
          └── auth fail → (removed)

tool call / refresh error → ERROR
```

#### Selectors

| Selector                       | Returns                                                   |
| ------------------------------ | --------------------------------------------------------- |
| `getConnectedServers(s)`       | `KlavisServer[]` where `status === CONNECTED`             |
| `getPendingAuthServers(s)`     | `KlavisServer[]` where `status === PENDING_AUTH`          |
| `getServerByIdentifier(id)(s)` | Single `KlavisServer`                                     |
| `isKlavisServer(id)(s)`        | Boolean                                                   |
| `getAllTools(s)`               | Flat `KlavisTool[]` from all connected servers            |
| `klavisAsLobeTools(s)`         | Converts `KlavisTool[]` to `LobeTool[]` for agent runtime |
| `isToolExecuting(toolId)(s)`   | Boolean — is a specific call in-flight                    |

#### SWR Sync

`useFetchUserKlavisServers()` — on mount, fetches the user's server list, deduplicates by `identifier` (keeps server with `CONNECTED` status over duplicates), and cleans up deprecated entries no longer returned by the API.

---

### 10.2 Ethos Skill Servers (LobehubSkill)

**Files:** `src/store/tool/slices/lobehubSkillStore/`

These are first-party Ethos-hosted skill providers accessed via OAuth scopes from the Ethos Market API.

#### Core Types

| Type                 | Key Fields                                                                                                                         |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `LobehubSkillServer` | `identifier`, `name`, `icon`, `isConnected`, `status`, `tools: LobehubSkillTool[]`, `providerUsername`, `scopes`, `tokenExpiresAt` |
| `LobehubSkillTool`   | `name`, `description`, `inputSchema`                                                                                               |
| `LobehubSkillStatus` | `CONNECTED`, `CONNECTING`, `ERROR`, `NOT_CONNECTED`                                                                                |

#### State (`LobehubSkillStoreState`)

```typescript
{
  lobehubSkillServers: LobehubSkillServer[];    // all connected providers
  lobehubSkillExecutingToolIds: Set<string>;    // tool call in-flight tracker
  lobehubSkillLoadingIds: Set<string>;          // providers being loaded
}
```

#### Connection Lifecycle

```
1. checkLobehubSkillStatus(identifier)
   → GET Market API /providers/:id/status
   → If connected: update server in state (or add new), status = CONNECTED
   → If not: status = NOT_CONNECTED

2. getLobehubSkillAuthorizeUrl(identifier)
   → Returns OAuth URL to open in browser

3. useFetchLobehubSkillConnections()   [SWR on mount]
   → GET Market API /user/connections
   → Dedup by identifier
   → For each connected server: refreshLobehubSkillTools()

4. refreshLobehubSkillToken(identifier)
   → POST Market API /providers/:id/refresh-token
   → Updates tokenExpiresAt in state

5. revokeLobehubSkill(identifier)
   → DELETE Market API /providers/:id/connection
   → Remove server from state
```

#### Status Transitions

```
checkLobehubSkillStatus()
  ├── connected    → CONNECTED
  └── not yet      → NOT_CONNECTED

tool call error (NOT_CONNECTED) → surface reconnect prompt
tool call error (TOKEN_EXPIRED) → refreshLobehubSkillToken() → retry

revokeLobehubSkill() → (removed from state)
```

#### Selectors

| Selector                       | Returns                                                   |
| ------------------------------ | --------------------------------------------------------- |
| `getConnectedServers(s)`       | `LobehubSkillServer[]` where `status === CONNECTED`       |
| `getServerByIdentifier(id)(s)` | Single `LobehubSkillServer`                               |
| `isLobehubSkillServer(id)(s)`  | Boolean                                                   |
| `getAllTools(s)`               | Flat `LobehubSkillTool[]` from connected servers          |
| `lobehubSkillAsLobeTools(s)`   | Converts to `LobeTool[]` for agent runtime                |
| `metaList(s)`                  | `LobeToolMeta[]` — consumed by `toolSelectors.metaList()` |
| `isToolExecuting(toolId)(s)`   | Boolean                                                   |

---

### 10.3 MCP Plugin Store (General)

**Files:** `src/store/tool/slices/mcpStore/`

This slice manages the **marketplace listing and installation** of MCP-compatible plugins (stdio or HTTP connections), distinct from Klavis's OAuth-based server model.

#### State (`MCPStoreState`)

```typescript
{
  activeMCPIdentifier?: string;
  categories: string[];
  currentPage: number;
  isMcpListInit?: boolean;
  listType: 'installed' | 'mcp';
  mcpInstallAbortControllers: Record<string, AbortController>;
  mcpInstallProgress: MCPInstallProgressMap;       // per-identifier progress
  mcpPluginItems: PluginItem[];
  mcpSearchKeywords?: string;
  mcpTestAbortControllers: Record<string, AbortController>;
  mcpTestErrors: Record<string, string>;
  mcpTestLoading: Record<string, boolean>;
  searchLoading?: boolean;
  totalCount?: number;
  totalPages?: number;
}
```

#### Installation State Machine

```
installMCPPlugin(identifier)
  ├── FETCHING_MANIFEST     → fetch plugin manifest from marketplace
  ├── CHECKING_INSTALLATION → check system deps / existing install
  ├── DEPENDENCIES_REQUIRED → (pause) surface dep install instructions
  ├── CONFIGURATION_REQUIRED→ (pause) show config form to user
  ├── GETTING_SERVER_MANIFEST → connect to server, retrieve tool manifest
  ├── INSTALLING_PLUGIN     → persist to installed plugins
  └── COMPLETED / ERROR

cancelInstallMCPPlugin(identifier) → abort via AbortController → cleanup progress
```

#### Connection Types (`McpConnection`)

```typescript
// stdio — local process
{ type: 'stdio', command: string, args?: string[], env?: Record<string, string> }

// http — remote SSE/HTTP server
{ type: 'http', url: string, headers?: Record<string, string> }

// cloud — hosted MCP endpoint
{ type: 'cloud', ... }
```

#### Key Actions

| Action                          | Behavior                                             |
| ------------------------------- | ---------------------------------------------------- |
| `installMCPPlugin(id)`          | Full installation flow with progress tracking        |
| `cancelInstallMCPPlugin(id)`    | Abort via `AbortController`, clean state             |
| `testMcpConnection(id, params)` | Validate stdio/http connection before install        |
| `cancelMcpConnectionTest(id)`   | Abort connection test                                |
| `uninstallMCPPlugin(id)`        | Uninstall and refresh plugin list                    |
| `resetMCPPluginList(keywords?)` | Clear list, optionally with new search               |
| `loadMoreMCPPlugins()`          | Paginate marketplace results                         |
| `useFetchMCPPluginList()`       | SWR hook — fetches and deduplicates marketplace list |

#### Key Selectors

| Selector                             | Returns                                           |
| ------------------------------------ | ------------------------------------------------- |
| `getMCPInstallProgress(id)(s)`       | `MCPInstallProgress` for given id                 |
| `isMCPInstalling(id)(s)`             | Boolean                                           |
| `isMCPInstallInProgress(id)(s)`      | True if currently in an active step               |
| `getMCPPluginRequiringConfig(id)(s)` | Config schema if step is `CONFIGURATION_REQUIRED` |
| `isMCPConnectionTesting(id)(s)`      | Boolean                                           |
| `getMCPConnectionTestError(id)(s)`   | Error string if test failed                       |

---

### 10.4 How MCP Servers Associate with Agents

All MCP server identifiers follow the same `agent.plugins[]` pattern as user skills and plugins:

```
User enables a Klavis / Ethos Skill / MCP plugin server
  → togglePlugin(server.identifier, true)
  → agent.plugins[] += server.identifier
  → updateAgentConfig() persists to DB

At runtime:
  → currentAgentPlugins(s) → [..., "klavis-github", "ethos-web-search"]
  → toolSelectors.availableToolsForDiscovery() resolves each identifier
      ├── Klavis: klavisStoreSelectors.klavisAsLobeTools()
      ├── LobehubSkill: lobehubSkillStoreSelectors.lobehubSkillAsLobeTools()
      └── MCP plugin: from installedPlugins manifest
  → Tools injected into agent context for LLM invocation
```

#### Deduplication Guard (in `availableToolsForDiscovery`)

```typescript
const klavisIds = new Set(s.servers.map((s) => s.identifier));
const lobehubSkillIds = new Set(s.lobehubSkillServers.map((s) => s.identifier));
const agentSkillIds = new Set(s.agentSkills.map((s) => s.identifier));

// installedPlugins excludes all three sets to prevent double-counting
s.installedPlugins
  .filter((p) => !klavisIds.has(p.identifier))
  .filter((p) => !lobehubSkillIds.has(p.identifier))
  .filter((p) => !agentSkillIds.has(p.identifier));
```

---

### 10.5 MCP vs Klavis vs Ethos Skill — Comparison

| Dimension             | Klavis MCP                      | Ethos Skill Server            | MCP Plugin (mcpStore)          |
| --------------------- | ------------------------------- | ----------------------------- | ------------------------------ |
| **Provider**          | Third-party via Klavis platform | Ethos-hosted first-party      | Any MCP-compatible server      |
| **Auth**              | OAuth (per-server)              | OAuth (Ethos Market)          | None / custom headers          |
| **Connection**        | Cloud (via Klavis API)          | Cloud (via Market API)        | stdio, http, or cloud          |
| **Store slice**       | `klavisStore`                   | `lobehubSkillStore`           | `mcpStore` + `plugin`          |
| **Status tracking**   | `KlavisServerStatus`            | `LobehubSkillStatus`          | `MCPInstallStep`               |
| **Token refresh**     | Not applicable                  | `refreshLobehubSkillToken()`  | Not applicable                 |
| **Tool format**       | `KlavisTool → LobeTool`         | `LobehubSkillTool → LobeTool` | Plugin manifest tools          |
| **Agent association** | `agent.plugins[]` identifier    | `agent.plugins[]` identifier  | `agent.plugins[]` identifier   |
| **Discovery UI**      | Tool picker (connected only)    | Tool picker (connected only)  | MCP marketplace + install flow |

---

## 11. Worked Example: Google Calendar via Klavis MCP

This walks through the complete lifecycle of enabling and using the **Google Calendar** Klavis MCP server on an agent — from first click to a tool call result.

---

### Step 1 — Server registration in constants

`packages/const/src/klavis.ts` declares the server as a static entry in `KLAVIS_SERVER_TYPES`:

```typescript
{
  author: 'Klavis',
  authorUrl: 'https://klavis.io',
  description: 'Google Calendar is a time-management and scheduling calendar service',
  icon: 'https://hub-apac-1.lobeobjects.space/assets/logos/googlecalendar.svg',
  identifier: 'google-calendar',          // stored in agent.plugins[]
  label: 'Google Calendar',
  serverName: Klavis.McpServerName.GoogleCalendar,  // sent to Klavis API
  readme: 'Integrate Google Calendar to view, create, and manage...',
}
```

`identifier` is the stable string that travels everywhere: Zustand state, DB column, and `agent.plugins[]`.

---

### Step 2 — User connects the server (OAuth)

```
User clicks "Connect" on Google Calendar in the tool picker
  → createKlavisServer({
      userId,
      serverName: Klavis.McpServerName.GoogleCalendar,
      identifier: 'google-calendar'
    })
  → POST /api/klavis/servers (klavisService.createServerInstance)
  → Klavis platform provisions a server instance, returns:
      {
        identifier: 'google-calendar',
        instanceId: 'kl_abc123',
        isAuthenticated: false,
        oauthUrl: 'https://accounts.google.com/o/oauth2/...',
        serverName: 'Google Calendar',
        serverUrl: 'https://mcp.klavis.io/instances/kl_abc123'
      }

State after createKlavisServer():
  servers: [{
    identifier: 'google-calendar',
    instanceId: 'kl_abc123',
    isAuthenticated: false,
    oauthUrl: 'https://accounts.google.com/...',
    serverUrl: 'https://mcp.klavis.io/instances/kl_abc123',
    status: KlavisServerStatus.PENDING_AUTH,   // ← not yet authorized
    tools: []
  }]
```

The UI opens `oauthUrl` in a popup for the user to grant Google Calendar access.

---

### Step 3 — OAuth completes

```
User grants access in Google OAuth popup
  → OAuth redirect triggers completeKlavisServerAuth('google-calendar')
  → refreshKlavisServerTools('google-calendar')
      ├── klavisService.getServerInstance({ instanceId: 'kl_abc123' })
      │     → { isAuthenticated: true }
      ├── klavisService.listTools({ serverUrl: 'https://mcp.klavis.io/instances/kl_abc123' })
      │     → { tools: [
      │         { name: 'list_events',   description: 'List calendar events', inputSchema: {...} },
      │         { name: 'create_event',  description: 'Create a new event',   inputSchema: {...} },
      │         { name: 'delete_event',  description: 'Delete an event',      inputSchema: {...} },
      │         ...
      │       ]}
      └── klavisService.updateKlavisPlugin({ identifier, isAuthenticated: true, tools, ... })
            → persists to installed_plugins table

State after refreshKlavisServerTools():
  servers[0].status = KlavisServerStatus.CONNECTED
  servers[0].isAuthenticated = true
  servers[0].tools = [list_events, create_event, delete_event, ...]
```

---

### Step 4 — User adds Google Calendar to an agent

```
User clicks "Add to Agent" (or agent auto-discovery selects it)
  → togglePlugin('google-calendar', true)
  → agent.plugins = [...existingPlugins, 'google-calendar']
  → updateAgentConfig(newConfig)  → persists to agents table in DB
```

At this point the DB has:

```sql
agents WHERE id = 'agent-xyz'
  plugins = '["web-search", "google-calendar"]'
```

---

### Step 5 — Tool discovery at runtime

When the agent chat session loads:

```
currentAgentPlugins(s)  →  ["web-search", "google-calendar"]

displayableAgentPlugins(s)
  → filterToolIds(["web-search", "google-calendar"])
  → both pass (neither is LocalSystem) → ["web-search", "google-calendar"]

toolSelectors.availableToolsForDiscovery(s) includes:
  ...
  {
    identifier: 'google-calendar',
    name: 'Google Calendar',
    description: 'Google Calendar is a time-management and scheduling calendar service'
  }
  ← from s.servers where status === CONNECTED

klavisStoreSelectors.klavisAsLobeTools(s)
  → converts KlavisTool[] to LobeTool[] format
  → injected into agent's tool context for the LLM
```

---

### Step 6 — LLM invokes a tool

User message: _"What meetings do I have tomorrow?"_

```
LLM decides to call: list_events
  → tool call dispatched to callKlavisTool({
      serverUrl: 'https://mcp.klavis.io/instances/kl_abc123',
      toolName: 'list_events',
      toolArgs: { timeMin: '2026-06-01T00:00:00Z', timeMax: '2026-06-01T23:59:59Z' }
    })
  → executingToolIds.add('https://mcp.klavis.io/instances/kl_abc123:list_events')
  → klavisService.callTool({ serverUrl, toolName, toolArgs })
      → POST to Klavis MCP proxy → Google Calendar API
      → returns: { items: [{ summary: 'Team standup', start: '09:00' }, ...] }
  → executingToolIds.delete(toolId)
  → { data: { items: [...] }, success: true }

LLM formats the response and replies to the user.
```

---

### Step 7 — Cleanup: deprecated server handling

When `useFetchUserKlavisServers()` runs on next app load, it compares stored identifiers against `VALID_KLAVIS_IDENTIFIERS`. If a server (e.g. the old `github` Klavis entry, now moved to Ethos Skill) is no longer in the list:

```
deprecatedPlugins = validPlugins.filter(p => !VALID_KLAVIS_IDENTIFIERS.has(p.identifier))

For each deprecated plugin:
  → klavisService.deleteServerInstance({ identifier, instanceId })
      → removes remote Klavis instance + local DB record
  → console.info('[Klavis] Cleaned up deprecated server: github')
```

This keeps the server list in sync with the curated `KLAVIS_SERVER_TYPES` constant without user action.

---

### Full state snapshot for `google-calendar`

| Layer                          | Value                                                                |
| ------------------------------ | -------------------------------------------------------------------- |
| `KLAVIS_SERVER_TYPES` constant | `{ identifier: 'google-calendar', serverName: GoogleCalendar, ... }` |
| Zustand `servers[]`            | `{ identifier, instanceId, status: CONNECTED, tools: [...] }`        |
| `installed_plugins` DB row     | `customParams.klavis = { instanceId, isAuthenticated: true, tools }` |
| `agents.plugins[]`             | `[..., "google-calendar"]`                                           |
| Tool available to LLM          | `list_events`, `create_event`, `delete_event`, ...                   |

---

## 12. Builtin Tools Integration

Builtin tools are first-party capabilities shipped directly with Ethos — no install, no OAuth. Each tool is defined once as a self-contained package under `packages/builtin-tools/src/<tool>/` and wired into both a **frontend executor registry** and a **server runtime registry**. At chat time, the `ToolsEngine` decides which builtins are enabled for the current agent and model.

---

### 12.1 Anatomy of a Builtin Tool Package

Every builtin tool lives under `packages/builtin-tools/src/<identifier>/` and exports four artefacts:

| File                | Purpose                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| `manifest.ts`       | API definitions, parameter schemas, metadata (title, avatar, description)                            |
| `types.ts`          | TypeScript interfaces for each API's params and state, plus the `Identifier` and `ApiName` constants |
| `systemRole.ts`     | System prompt injected into the agent context when the tool is enabled                               |
| `executor/index.ts` | Frontend executor class — implements each API method (usually delegates to backend via REST)         |

All tools are re-exported from the package root `packages/builtin-tools/src/index.ts` and assembled into the `builtinTools` array in `packages/builtin-tools/src/builtinTools.ts`.

---

### 12.2 Tool Registry Constants

**File:** `packages/builtin-tools/src/builtinTools.ts`

| Constant                   | Description                                                                                              |
| -------------------------- | -------------------------------------------------------------------------------------------------------- |
| `builtinTools`             | Full registry — one entry per tool with `identifier`, `manifest`, `discoverable` flag, `type: 'builtin'` |
| `defaultToolIds`           | Tools enabled by default (WebBrowsing, KnowledgeBase, Memory, LocalSystem, CloudSandbox, …)              |
| `alwaysOnToolIds`          | Always active regardless of agent config (Activator, Skills, SkillStore)                                 |
| `manualModeExcludeToolIds` | Tools suppressed in manual-mode conversations                                                            |
| `runtimeManagedToolIds`    | Tools whose enabled state is controlled by the `ToolsEngine`, not the user                               |

---

### 12.3 Frontend: Store Slice

**Files:** `src/store/tool/slices/builtin/`

**State:**

```typescript
interface BuiltinToolState {
  builtinTools: LobeBuiltinTool[]; // loaded from @lobechat/builtin-tools
  builtinSkills: BuiltinSkill[]; // builtin skills from API
  builtinToolLoading: Record<string, boolean>; // per-executor loading flags
  uninstalledBuiltinTools: string[]; // identifiers disabled by the user
  uninstalledBuiltinToolsLoading: boolean;
}
```

**Key actions:**

| Action                                        | Behavior                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `invokeBuiltinTool(id, apiName, params, ctx)` | Looks up executor, sets loading flag, calls `invokeExecutor()`, returns `BuiltinToolResult` |
| `installBuiltinTool(id)`                      | Removes from `uninstalledBuiltinTools`, persists preference                                 |
| `uninstallBuiltinTool(id)`                    | Adds to `uninstalledBuiltinTools`, persists preference                                      |
| `useFetchUninstalledBuiltinTools()`           | SWR — loads user's disabled-tool list on mount                                              |
| `useFetchBuiltinSkills()`                     | SWR — loads builtin skills via `agentSkillService.listBuiltin()`                            |

---

### 12.4 Frontend: Executor Registry

**File:** `src/store/tool/slices/builtin/executors/index.ts`

```typescript
const executorRegistry = new Map<string, IBuiltinToolExecutor>();

// Registered on module load:
// From @lobechat/builtin-tools:
//   calculator, agentBuilder, cloudSandbox, creds, cron, …
// From local files:
//   activator, agentDocuments, webBrowsing, skills, …

getExecutor(identifier); // → IBuiltinToolExecutor | undefined
hasExecutor(identifier, api); // → boolean
invokeExecutor(id, api, params, ctx); // → BuiltinToolResult
```

Each executor implements `IBuiltinToolExecutor` — a class with one method per API name. Most frontend executors are thin: they construct a REST payload and POST to `/tools/run`, letting the server do the actual work. Some (e.g. WebBrowsing) do real work on the frontend through injected services.

---

### 12.5 Server: Runtime Registry

**File:** `src/server/services/toolExecution/serverRuntimes/index.ts`

```typescript
const serverRuntimeFactories = new Map<string, ServerRuntimeFactory>();

// Registered runtimes (20+):
// calculator, webBrowsing, cloudSandbox, memory, activator,
// agentDocuments, notebook, skillStore, skills, message,
// localSystem, remoteDevice, brief, task, topicReference,
// userInteraction, creds, cron, gtd, agentMarketplace, lobeAgent

getServerRuntime(identifier, context); // → runtime instance (sync or async)
```

Each `ServerRuntimeFactory` is a `{ identifier, factory: (context) => runtime }` tuple. The factory receives the full `ToolExecutionContext` (userId, topicId, serverDB, …) and returns a runtime object whose methods map 1:1 to the tool's API names.

---

### 12.6 Server: Execution Service

```
ToolExecutionService.executeTool(payload, context)
  ├── payload.type === 'mcp'      → mcpService.callTool()
  └── payload.type === 'builtin'  → BuiltinToolsExecutor.execute()
        ├── source === 'lobehubSkill' → marketService.executeLobehubSkill()
        ├── source === 'klavis'       → klavisService.executeKlavisTool()
        └── builtin                  → getServerRuntime(identifier, context)
                                          → runtime[apiName](args, context)

Returns: { content, state, error, executionTime, success }
  content is truncated to toolResultMaxLength (default 6000 chars)
```

---

### 12.7 ToolsEngine — Enabling Builtins for an Agent

**File:** `src/server/modules/Mecha/AgentToolsEngine/index.ts`

At the start of each agent run, `createServerAgentToolsEngine()` assembles the active tool set:

```
Inputs:
  - agent.plugins[]       → user-selected tool identifiers
  - builtinTools registry → all manifests
  - agent config          → model, runtimeMode, knowledgeBases, memory settings

Enable rules (applied on top of user plugins):
  alwaysOnToolIds         → always enabled (Activator, Skills, SkillStore)
  CloudSandbox            → if runtimeMode === 'cloud'
  KnowledgeBase           → if agent has knowledgeBases configured
  LocalSystem             → if runtimeMode === 'local' AND (client executor OR device proxy online)
  Memory                  → if global memory enabled
  Message                 → if conversation is a bot channel
  WebBrowsing             → if search is enabled in server config
```

The resulting manifest set is passed to the LLM as available tools.

---

### 12.8 Worked Example: Calculator

**Identifier:** `lobe-calculator`\
**Package:** `packages/builtin-tools/src/calculator/`

#### Manifest — 10 APIs

```typescript
// packages/builtin-tools/src/calculator/manifest.ts
CalculatorManifest = {
  identifier: 'lobe-calculator',
  meta: { avatar: '🧮', title: 'Calculator', description: '...' },
  api: [
    { name: 'calculate', description: 'Direct math expressions & unit conversions' },
    { name: 'evaluate', description: 'Complex expressions with variable substitution' },
    { name: 'sort', description: 'Sort numbers ascending/descending' },
    { name: 'base', description: 'Number base conversion (2–36)' },
    { name: 'differentiate', description: 'Compute derivatives' },
    { name: 'defintegrate', description: 'Definite integrals' },
    { name: 'integrate', description: 'Indefinite integrals' },
    { name: 'execute', description: 'Generic nerdamer expressions' },
    { name: 'limit', description: 'Compute limits' },
    { name: 'solve', description: 'Algebraic equations & systems' },
  ],
};
```

#### Types

```typescript
// packages/builtin-tools/src/calculator/types.ts
export const CalculatorIdentifier = 'lobe-calculator';

export const CalculatorApiName = {
  calculate: 'calculate',
  evaluate: 'evaluate',
  solve: 'solve',
  // ... all 10
};

export interface CalculateParams {
  expression: string;
}
export interface CalculateState {
  result: string | number;
}
// ... one Params + State pair per API
```

#### Frontend Executor

```typescript
// packages/builtin-tools/src/calculator/executor/index.ts
class CalculatorExecutor extends BaseExecutor {
  identifier = CalculatorIdentifier;

  private async runPythonCalculator(apiName: string, params: unknown) {
    const response = await POST('/tools/run', {
      tool_name: `${CalculatorIdentifier}__${apiName}`, // "lobe-calculator__calculate"
      arguments: params,
    });
    return JSON.parse(response.result) as BuiltinToolResult;
  }

  calculate = (params: CalculateParams) =>
    this.runPythonCalculator(CalculatorApiName.calculate, params);

  solve = (params: SolveParams) => this.runPythonCalculator(CalculatorApiName.solve, params);

  // ... same pattern for all 10 APIs
}
```

All 10 methods delegate to `runPythonCalculator()` — the executor is purely a transport layer.

#### Server Runtime

```typescript
// src/server/services/toolExecution/serverRuntimes/calculator.ts
class CalculatorPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    const response = await callPythonBackend('/api/tools/run', this.context.userId, {
      body: {
        tool_name: `${CalculatorIdentifier}__${apiName}`,
        arguments: args,
      },
    });
    return JSON.parse(response.result);
  }

  calculate = (args: unknown) => this.run(CalculatorApiName.calculate, args);
  solve = (args: unknown) => this.run(CalculatorApiName.solve, args);
  // ... all 10
}

export const calculatorRuntime: ServerRuntimeRegistration = {
  identifier: CalculatorIdentifier,
  factory: (context) => new CalculatorPythonRuntime(context),
};
```

#### End-to-End Call Trace

User message: _"What is the integral of x² from 0 to 3?"_

```
1. LLM emits tool call:
     { name: 'lobe-calculator__defintegrate',
       args: { expression: 'x^2', variable: 'x', lowerBound: '0', upperBound: '3' } }

2. Frontend:
   invokeBuiltinTool('lobe-calculator', 'defintegrate', args, ctx)
     → executorRegistry.get('lobe-calculator')  →  CalculatorExecutor
     → executor.defintegrate(args)
     → runPythonCalculator('defintegrate', args)
     → POST /tools/run  { tool_name: 'lobe-calculator__defintegrate', arguments: args }

3. Server — ToolExecutionService.executeTool():
     payload.type === 'builtin'
     → BuiltinToolsExecutor.execute()
     → getServerRuntime('lobe-calculator', context)
         → new CalculatorPythonRuntime(context)
     → runtime.defintegrate(args)
     → callPythonBackend('/api/tools/run', userId, { tool_name, arguments })

4. Python backend:
     Evaluates definite integral of x² from 0 to 3
     → result: "9"

5. Response chain:
     CalculatorPythonRuntime → { result: "9" }
     BuiltinToolsExecutor    → { content: "9", success: true }
     ToolExecutionService    → { content: "9", executionTime: 120, success: true }
     REST response           → frontend

6. Frontend:
     BuiltinToolResult { content: "9", success: true }
     Chat message rendered: "The definite integral of x² from 0 to 3 is 9."
```

#### State snapshot for `lobe-calculator`

| Layer                | Value                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------ |
| `builtinTools` array | `{ identifier: 'lobe-calculator', type: 'builtin', discoverable: true, manifest: CalculatorManifest }` |
| `agent.plugins[]`    | `[..., "lobe-calculator"]` (or enabled by default)                                                     |
| Frontend executor    | `CalculatorExecutor` — registered in `executorRegistry`                                                |
| Server runtime       | `CalculatorPythonRuntime` — instantiated per request via `calculatorRuntime.factory`                   |
| Execution target     | Python backend at `/api/tools/run`                                                                     |
| Tool name format     | `lobe-calculator__<apiName>`                                                                           |

---

### 12.9 Builtin vs Klavis MCP vs Agent Skill — Comparison

| Dimension             | Builtin Tool                              | Klavis MCP                          | Agent Skill                    |
| --------------------- | ----------------------------------------- | ----------------------------------- | ------------------------------ |
| **Packaging**         | `packages/builtin-tools/src/<id>/`        | `KLAVIS_SERVER_TYPES` constant      | `agent_skills` DB table        |
| **Auth**              | None                                      | OAuth per server                    | None (user-owned)              |
| **Enabled by**        | Default / `agent.plugins[]`               | `agent.plugins[]` after connect     | `agent.plugins[]` after import |
| **Frontend executor** | Class in executor registry                | `klavisService.callTool()`          | No frontend executor           |
| **Server runtime**    | Factory in serverRuntimes registry        | `klavisService.executeKlavisTool()` | Content injected into context  |
| **Tool definition**   | Manifest shipped in code                  | Tools fetched live from Klavis API  | `SkillManifest` in DB          |
| **System prompt**     | `systemRole.ts` per tool                  | Not applicable                      | `content` field from DB        |
| **Discoverable**      | Controlled by `discoverable` flag         | Always (when connected)             | Dedicated skills panel         |
| **Install/uninstall** | User preference (uninstalledBuiltinTools) | Connect/disconnect OAuth            | Import/delete from library     |

---

## 13. HTTP API Contracts

### 13.1 Klavis REST Routes (Python FastAPI)

**File:** `python-backend/app/routers/klavis.py`\
**Prefix:** `/api/klavis`\
**Auth:** Every endpoint calls `Depends(get_current_user_id)` — the TypeScript backend forwards the authenticated `userId` via `X-Internal-User-Id` header, validated by `PYTHON_BACKEND_SERVICE_TOKEN`.

External Klavis API calls are made with `Authorization: Bearer <KLAVIS_API_KEY>` via `_klavis_request()`.

| Method | Path                      | Request Body                                                                      | Response                                                                              | Description                                                                        |
| ------ | ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `POST` | `/create-server-instance` | `{ identifier, server_name, user_id }`                                            | `{ identifier, instanceId, isAuthenticated, oauthUrl, serverUrl, serverName, tools }` | Creates a Klavis MCP instance, fetches tools, saves to `user_installed_plugins`    |
| `POST` | `/delete-server-instance` | `{ identifier, instance_id }`                                                     | `{ success: true }`                                                                   | Deletes instance from Klavis API and removes DB row                                |
| `GET`  | `/plugins`                | —                                                                                 | `PluginRow[]`                                                                         | Returns all rows from `user_installed_plugins` where `custom_params.klavis` is set |
| `POST` | `/tools/call`             | `{ server_url, tool_name, tool_args? }`                                           | `{ content, state, success }`                                                         | Proxies tool call to Klavis `/mcp/call-tool`                                       |
| `GET`  | `/tools`                  | `?server_name=Gmail`                                                              | `{ tools: KlavisTool[] }`                                                             | Fetches tool list by server name from Klavis API                                   |
| `GET`  | `/tools/list`             | `?server_url=...`                                                                 | `{ tools: KlavisTool[] }`                                                             | Lists tools from a live server instance URL                                        |
| `GET`  | `/server-instance`        | `?instanceId=...`                                                                 | `{ instanceId, isAuthenticated, authNeeded, oauthUrl, ... }`                          | Gets instance status; maps `AUTH_ERROR` to structured error response               |
| `GET`  | `/user-integrations`      | `?userId=...`                                                                     | `{ integrations: [] }`                                                                | Gets Klavis user integrations                                                      |
| `POST` | `/update-plugin`          | `{ identifier, instance_id, is_authenticated, server_name, server_url, tools[] }` | `{ savedCount }`                                                                      | Upserts `user_installed_plugins` row with new manifest + `custom_params.klavis`    |
| `POST` | `/remove-plugin`          | `{ identifier }`                                                                  | `{ success: true }`                                                                   | Deletes row from `user_installed_plugins`                                          |

**`custom_params.klavis` shape stored in `user_installed_plugins`:**

```json
{
  "klavis": {
    "instanceId": "kl_abc123",
    "isAuthenticated": true,
    "oauthUrl": null,
    "serverName": "Google Calendar",
    "serverUrl": "https://mcp.klavis.io/instances/kl_abc123"
  }
}
```

**Manifest shape stored in `user_installed_plugins.manifest`:**

```json
{
  "api": [
    {
      "name": "list_events",
      "description": "...",
      "parameters": { "type": "object", "properties": {} }
    }
  ],
  "identifier": "google-calendar",
  "meta": {
    "avatar": "🔌",
    "title": "Google Calendar",
    "description": "Ethos Mcp Server: Google Calendar"
  },
  "type": "default"
}
```

---

### 13.2 Tool Execution REST Route (Python FastAPI)

**File:** `python-backend/app/routers/tools.py`\
**Prefix:** `/api/tools`

| Method | Path   | Request Body                          | Response              | Description                             |
| ------ | ------ | ------------------------------------- | --------------------- | --------------------------------------- |
| `GET`  | \`\`   | —                                     | `{ tools: string[] }` | Lists all registered builtin tool names |
| `POST` | `/run` | `{ tool_name: str, arguments: dict }` | `{ result: any }`     | Executes a tool by name with arguments  |

**`tool_name` format:** `<identifier>__<apiName>` — e.g. `lobe-calculator__calculate`, `lobe-calculator__solve`

**Request example:**

```json
POST /api/tools/run
{
  "tool_name": "lobe-calculator__calculate",
  "arguments": { "expression": "2 * pi * 5" }
}
```

**Response example:**

```json
{ "result": "31.41592653589793" }
```

**Execution path inside Python:**

```python
execute_tool_call_with_context(tool_name, arguments, session, user_id)
  ├── Check context handlers (tools with double-underscore prefix like skills__findAll)
  ├── Handle agent CRUD tools via _handle_agent_tool()
  └── Fall back to generic execute_tool_call() for stateless tools
```

---

### 13.3 TypeScript → Python Proxy (`callPythonBackend`)

**File:** `src/server/utils/pythonBackend.ts`

The TypeScript backend is a reverse proxy — it never does math or memory operations itself. It delegates via `callPythonBackend()`:

```typescript
// Signature
callPythonBackend<T>(path: string, userId: string, opts?: CallOptions): Promise<T>

// Example — from calculator server runtime
await callPythonBackend<PythonToolRunResponse>('/api/tools/run', context.userId, {
  body: { tool_name: 'lobe-calculator__calculate', arguments: args },
})
```

**Auth headers sent to Python:**

```
X-Internal-User-Id: <userId>          // always present
X-Service-Token: <PYTHON_BACKEND_SERVICE_TOKEN>  // if configured
Content-Type: application/json
```

**Environment variables required:**

| Variable                       | Purpose                                                          | Required                                                |
| ------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------- |
| `PYTHON_BACKEND_URL`           | Base URL of Python FastAPI server (e.g. `http://localhost:8000`) | Yes — without it `callPythonBackend` throws immediately |
| `PYTHON_BACKEND_SERVICE_TOKEN` | Shared secret validating TS→Python trust                         | Recommended                                             |
| `KLAVIS_API_KEY`               | Klavis platform API key                                          | Required for Klavis MCP                                 |
| `KLAVIS_API_BASE_URL`          | Override Klavis API base (default: `https://api.klavis.ai`)      | Optional                                                |

**Stream variant** — `callPythonBackendStream()` returns a raw `Response` for SSE proxying (no timeout, no body parsing):

```typescript
const upstream = await callPythonBackendStream('/api/ai-agent/exec/stream', userId, { body });
// pipe upstream.body → client response
```

---

### 13.4 `user_installed_plugins` DB Schema

**File:** `src/database/schemas/user.ts`\
Klavis MCP servers and user-installed plugins both live here — NOT in `agent_skills`.

```
user_installed_plugins
├── user_id       TEXT    NOT NULL  FK → users.id (cascade delete)
├── identifier    TEXT    NOT NULL
├── type          TEXT    NOT NULL  ('plugin' | 'customPlugin')
├── manifest      JSONB             ToolManifest  (api[], meta, identifier, type)
├── settings      JSONB             per-plugin user settings
├── custom_params JSONB             CustomPluginParams — Klavis stores klavis: {...} here
├── source        VARCHAR(255)
├── created_at    TIMESTAMP
└── updated_at    TIMESTAMP

PRIMARY KEY: (user_id, identifier)
```

**Key distinction:**

| Table                    | Stores                                                                          |
| ------------------------ | ------------------------------------------------------------------------------- |
| `agent_skills`           | User-created / imported skills (SKILL.md, ZIP, GitHub)                          |
| `user_installed_plugins` | Installed plugins AND Klavis MCP servers (identified by `custom_params.klavis`) |

---

## 14. `IBuiltinToolExecutor` Interface & `BaseExecutor`

**File:** `packages/types/src/tool/builtin.ts` (lines 683–798)

### Interface

```typescript
export interface IBuiltinToolExecutor {
  readonly identifier: string;
  invoke(apiName: string, params: any, ctx: BuiltinToolContext): Promise<BuiltinToolResult>;
  hasApi(apiName: string): boolean;
  getApiNames(): string[];
}
```

### `BaseExecutor` Abstract Class

Subclasses only define `identifier`, `apiEnum`, and the business methods. Routing is automatic.

```typescript
export abstract class BaseExecutor<
  TApiEnum extends Record<string, string>,
> implements IBuiltinToolExecutor {
  abstract readonly identifier: string;
  protected abstract readonly apiEnum: TApiEnum; // e.g. CalculatorApiName

  // Auto-dispatches to this[apiName](params, ctx)
  invoke = async (apiName: string, params: any, ctx: BuiltinToolContext) => {
    if (!this.hasApi(apiName))
      return { success: false, error: { type: 'ApiNotFound', message: `Unknown API: ${apiName}` } };

    const method = (this as any)[apiName];
    if (typeof method !== 'function')
      return {
        success: false,
        error: { type: 'MethodNotImplemented', message: `Method not implemented: ${apiName}` },
      };

    return method(params, ctx);
  };

  hasApi(apiName: string): boolean {
    return Object.values(this.apiEnum).includes(apiName);
  }

  getApiNames(): string[] {
    return Object.values(this.apiEnum);
  }
}
```

### Writing a New Builtin Tool

```typescript
// 1. Define ApiName enum and types
export const MyToolApiName = { compute: 'compute', transform: 'transform' } as const;
export const MyToolIdentifier = 'my-tool';

export interface ComputeParams {
  input: string;
}

// 2. Implement executor — extend BaseExecutor
export class MyToolExecutor extends BaseExecutor<typeof MyToolApiName> {
  readonly identifier = MyToolIdentifier;
  protected readonly apiEnum = MyToolApiName;

  // Method name MUST match the apiEnum value exactly
  compute = async (params: ComputeParams, ctx: BuiltinToolContext): Promise<BuiltinToolResult> => {
    // Option A: delegate to Python backend
    const res = await callPythonBackend('/api/tools/run', ctx.userId, {
      body: { tool_name: `${MyToolIdentifier}__compute`, arguments: params },
    });
    return { success: true, content: String(res) };

    // Option B: run logic locally
    return { success: true, content: params.input.toUpperCase() };
  };

  transform = async (params: unknown, ctx: BuiltinToolContext): Promise<BuiltinToolResult> => {
    // ...
  };
}

// 3. Register in frontend executor registry
//    src/store/tool/slices/builtin/executors/index.ts
executorRegistry.set(MyToolIdentifier, new MyToolExecutor());

// 4. Register server runtime
//    src/server/services/toolExecution/serverRuntimes/myTool.ts
export const myToolRuntime: ServerRuntimeRegistration = {
  identifier: MyToolIdentifier,
  factory: (context) => new MyToolServerRuntime(context),
};
//    src/server/services/toolExecution/serverRuntimes/index.ts
serverRuntimeFactories.set(MyToolIdentifier, myToolRuntime.factory);

// 5. Add manifest to packages/builtin-tools/src/myTool/manifest.ts
//    and register in packages/builtin-tools/src/builtinTools.ts
```

### `BuiltinToolResult` type

```typescript
interface BuiltinToolResult {
  success: boolean;
  content?: string; // serialized result shown to the LLM
  state?: any; // optional UI state for rendering
  error?: {
    type: string;
    message: string;
  };
}
```

### `BuiltinToolContext` type

```typescript
interface BuiltinToolContext {
  agentId?: string;
  groupId?: string | null;
  topicId?: string;
  threadId?: string | null;
  documentId?: string | null;
  taskId?: string;
  scope?: string | null;
  messageId?: string;
  operationId?: string;
  activeDeviceId?: string;
  memoryToolPermission?: 'read-only' | 'read-write';
  toolManifestMap: Record<string, LobeToolManifest>;
  toolResultMaxLength?: number; // default 6000 chars
  serverDB?: LobeChatDatabase;
  userId?: string;
  signal?: AbortSignal;
}
```

---

## 15. Skill-to-System-Prompt Injection

This is the last-mile that makes a skill's `content` actually influence the LLM. Two services handle it client-side before the chat request is sent.

---

### 15.1 `resolveClientSkills` — Build the Skill Inventory

**File:** `src/services/chat/mecha/skillEngineering.ts`

Called once per chat operation to build the `OperationSkillSet` that tells the agent which skills are available.

```typescript
resolveClientSkills(pluginIds?: string[]): OperationSkillSet

// Sources:
// 1. toolStore.builtinSkills  — platform-shipped skills (e.g. Artifacts)
// 2. toolStore.agentSkills    — user-created / market-imported skills

const skillEngine = new SkillEngine({
  enableChecker: (skill) => isBuiltinSkillAvailableInCurrentEnv(skill.identifier),
  skills: [...builtinMetas, ...dbMetas],
})

return skillEngine.generate(pluginIds ?? [])
// generates OperationSkillSet — the intersection of available skills and agent's pluginIds
```

`isBuiltinSkillAvailableInCurrentEnv` filters platform-specific skills (e.g. a desktop-only browser skill is excluded in web context).

---

### 15.2 `resolveSelectedSkillsWithContent` — Inject Skill Content

**File:** `src/services/chat/mecha/skillPreload.ts`

Called when the user's message references specific skills (via `<skill name="..." />` tags). Enriches each referenced skill with its full `content` string so the `SelectedSkillInjector` can inline it into the system prompt.

```typescript
resolveSelectedSkillsWithContent({
  message: string,
  selectedSkills?: RuntimeSelectedSkill[],
  userCreds?: UserCredSummary[],
}): Promise<RuntimeSelectedSkill[]>
```

**Step-by-step:**

```
1. resolveSelectedSkills(message, selectedSkills)
   ├── Merge explicitly passed selectedSkills[]
   └── Extract skills from message text via two regex patterns:
         <skill name="my-skill" label="My Skill" />          ← current format
         <action type="my-skill" category="skill" label="My Skill" />  ← legacy format
   → Deduplicate by identifier

2. For each resolved skill → loadSkillContent(skill, userCreds):

   A. Check toolStore.builtinSkills first (in-memory, no fetch)
      → If found and it's the Creds skill:
           inject UserCredsContext into content via injectCredsContext()
      → Return { identifier, name, content }

   B. Check toolStore.agentSkills (list item) + agentSkillDetailMap (cached detail)
      → Cache hit: use agentSkillDetailMap[id].content directly
      → Cache miss: agentSkillService.getById(id) or getByIdentifier(identifier)
      → If skill has resources:
           content += '\n\n' + resourcesTreePrompt(name, resources)
      → Return { identifier, name, content }

3. Merge content back into RuntimeSelectedSkill[]
   → { identifier, name, content: '<full skill markdown>' }
```

**Skill tag format in messages:**

```
<skill name="my-data-analyst" label="Data Analyst" />
```

The `name` attribute matches `skill.identifier`; `label` is the display name.

---

### 15.3 Full Injection Flow

```
User sends message: "Analyse this CSV <skill name="data-analyst" label="Data Analyst" />"

1. skillEngineering.resolveClientSkills(agent.plugins)
   → OperationSkillSet: { available: ['data-analyst', 'web-search', ...] }

2. skillPreload.resolveSelectedSkillsWithContent({ message, selectedSkills, userCreds })
   → Parses <skill name="data-analyst" /> from message
   → loadSkillContent('data-analyst'):
       → not in builtinSkills
       → found in agentSkills list → agentSkillService.getById(id)
       → returns content: "You are a data analysis expert..."
   → Returns: [{ identifier: 'data-analyst', name: 'Data Analyst', content: '...' }]

3. SelectedSkillInjector (context-engine)
   → Receives RuntimeSelectedSkill[] with content attached
   → Inlines skill content into the system prompt:
       "You are a data analysis expert..."
       + original agent system prompt

4. LLM receives enriched system prompt
   → Behaves as the Data Analyst skill instructs
```

**Key rule:** if `content` is present on `RuntimeSelectedSkill`, the injector inlines it directly. If not (e.g. fetch failed), it falls back to constructing `activateSkill` tool-call preload messages instead.

---

## 16. Service Layer Class Map

| Class / Module                | File                                                   | Responsibility                                                   |
| ----------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------- |
| `AgentSkillsActionImpl`       | `src/store/tool/slices/agentSkills/action.ts`          | Zustand actions; orchestrates service calls + state updates      |
| `agentSkillsSelectors`        | `src/store/tool/slices/agentSkills/selectors.ts`       | Read state; format for UI and tool discovery                     |
| `agentSkillRouter`            | `src/server/routers/lambda/agentSkills.ts`             | TRPC endpoint definitions                                        |
| `SkillImporter`               | `src/server/services/skill/importer.ts`                | Import orchestration; dedup; storage                             |
| `SkillParser`                 | `src/server/services/skill/parser.ts`                  | SKILL.md / ZIP parsing; manifest validation                      |
| `SkillResourceService`        | `src/server/services/skill/resource.ts`                | Resource file CRUD (S3-backed)                                   |
| `AgentSkillModel`             | `src/database/models/agentSkill.ts`                    | Drizzle ORM CRUD for `agent_skills` table                        |
| `PluginSliceActionImpl`       | `src/store/agent/slices/plugin/action.ts`              | `togglePlugin` — adds/removes identifiers from `agent.plugins[]` |
| `toolSelectors`               | `src/store/tool/selectors/tool.ts`                     | Unified tool discovery across all sources                        |
| `KlavisStoreActionImpl`       | `src/store/tool/slices/klavisStore/action.ts`          | Klavis server lifecycle; OAuth flow; tool execution              |
| `klavisStoreSelectors`        | `src/store/tool/slices/klavisStore/selectors.ts`       | Server/tool queries; `klavisAsLobeTools()` conversion            |
| `LobehubSkillStoreActionImpl` | `src/store/tool/slices/lobehubSkillStore/action.ts`    | Ethos Skill server lifecycle; token management; tool execution   |
| `lobehubSkillStoreSelectors`  | `src/store/tool/slices/lobehubSkillStore/selectors.ts` | Server/tool queries; `lobehubSkillAsLobeTools()` conversion      |
| `PluginMCPStoreActionImpl`    | `src/store/tool/slices/mcpStore/action.ts`             | MCP plugin install state machine; connection testing             |
| `mcpStoreSelectors`           | `src/store/tool/slices/mcpStore/selectors.ts`          | Install progress; config requirements; connection test state     |
