# Ethos Architecture

> Comprehensive architecture reference for the Ethos monorepo.

## Table of Contents

- [System Overview](#system-overview)
- [Tech Stack](#tech-stack)
- [Monorepo Structure](#monorepo-structure)
- [Frontend Architecture](#frontend-architecture)
- [Backend Architecture](#backend-architecture)
- [Database Layer](#database-layer)
- [Data Flow](#data-flow)
- [Build System](#build-system)
- [Deployment](#deployment)
- [Feature Flags](#feature-flags)
- [Packages](#packages)
- [Key Design Decisions](#key-design-decisions)

---

## System Overview

Ethos is an open-source AI agent framework that combines a conversational UI, multi-model AI backend, plugin/skill ecosystem, and enterprise configurability into a single full-stack application.

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Browser)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Vite    │  │  React   │  │  Zustand  │  │  SWR /     │  │
│  │  SPA     │──│  Router  │──│  Stores   │──│  Services  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────┬──────┘  │
│                                                   │         │
└───────────────────────────────────────────────────┼─────────┘
                                                    │ TRPC / REST
┌───────────────────────────────────────────────────┼─────────┐
│                     Hono Server (Node.js)         │         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────┴──────┐  │
│  │  Auth    │  │  TRPC    │  │  REST     │  │  SPA       │  │
│  │  Routes  │  │  Routers │  │  Handlers │  │  Serving   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────────┘  │
│       │              │              │                        │
│  ┌────┴──────────────┴──────────────┴────┐                  │
│  │         Server Services Layer         │                  │
│  └────────────────┬──────────────────────┘                  │
│                   │                                         │
│  ┌────────────────┴──────────────────────┐                  │
│  │         Server Modules Layer          │                  │
│  │  (AgentRuntime, S3, KeyVaults, etc.)  │                  │
│  └────────────────┬──────────────────────┘                  │
└───────────────────┼─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───┴───┐     ┌─────┴────┐   ┌─────┴────┐
│ Postgres│   │  Redis   │   │   S3     │
│ (Drizzle)│  │ (Cache)  │   │ (Files)  │
└─────────┘   └──────────┘   └──────────┘
```

---

## Tech Stack

| Layer                  | Technology                                                          |
| ---------------------- | ------------------------------------------------------------------- |
| **Frontend framework** | React 19 + TypeScript                                               |
| **SPA bundler**        | Vite (with Rolldown)                                                |
| **Client routing**     | react-router-dom                                                    |
| **State management**   | Zustand (slice pattern)                                             |
| **Data fetching**      | SWR (client), TRPC (type-safe RPC)                                  |
| **UI components**      | @lobehub/ui, Ant Design                                             |
| **Styling**            | antd-style (CSS-in-JS), prefer `createStaticStyles` with `cssVar.*` |
| **i18n**               | react-i18next                                                       |
| **Server framework**   | Hono (Node.js)                                                      |
| **API layer**          | TRPC (4 routers) + REST handlers                                    |
| **Auth**               | better-auth                                                         |
| **Database**           | PostgreSQL via Drizzle ORM                                          |
| **Caching**            | Redis (ioredis)                                                     |
| **File storage**       | S3-compatible object storage                                        |
| **Testing**            | Vitest + Playwright (E2E)                                           |
| **Package manager**    | pnpm (monorepo), bun (script runner)                                |

---

## Monorepo Structure

```
lobehub/
├── apps/                          # Standalone applications
│   ├── desktop/                   #   Electron desktop app
│   ├── cli/                       #   Ethos CLI (@lobehub/cli)
│   └── device-gateway/            #   Device gateway service
│
├── packages/                      # Shared packages (~72 packages)
│   ├── database/                  #   Drizzle schemas, models, repositories
│   ├── agent-runtime/             #   Agent execution runtime
│   ├── context-engine/            #   Context assembly for LLM calls
│   ├── model-runtime/             #   Multi-provider model abstraction
│   ├── model-bank/                #   Model metadata & capabilities
│   ├── types/                     #   Shared TypeScript types
│   ├── const/                     #   Shared constants
│   ├── utils/                     #   Shared utilities
│   ├── prompts/                   #   System prompt templates
│   ├── builtin-tool-*/            #   ~25 self-contained builtin tools
│   ├── chat-adapter-*/            #   Platform chat adapters (Feishu, QQ, WeChat, Line)
│   └── ...
│
├── src/                           # Main application source
│   ├── spa/                       #   SPA entry points + router config
│   ├── routes/                    #   SPA page segments (thin shells)
│   ├── features/                  #   Business components by domain (~75 domains)
│   ├── store/                     #   Zustand stores (~27 stores)
│   ├── services/                  #   Client-side service layer
│   ├── hooks/                     #   Shared React hooks
│   ├── components/                #   Shared UI components
│   ├── hono-server/               #   Hono server entry & route mounting
│   ├── handlers/                  #   API route handlers
│   ├── server/                    #   Server services, routers, modules
│   ├── libs/                      #   Infrastructure wrappers (trpc, swr, auth, redis)
│   ├── config/                    #   Feature flags, DB config, routes
│   ├── envs/                      #   Environment variable schemas
│   ├── locales/                   #   i18n locale source files
│   ├── layout/                    #   Global layout providers
│   ├── business/                  #   Cloud/commercial business logic
│   └── types/                     #   App-level type definitions
│
├── e2e/                           # E2E tests (Cucumber + Playwright)
├── docs/                          # Documentation (MDX)
├── locales/                       # Generated locale JSON files
├── scripts/                       # Build, CI, workflow scripts
├── docker-compose/                # Docker Compose configs (dev + deploy)
├── plugins/                       # Vite plugins
└── public/                        # Static assets
```

---

## Frontend Architecture

### SPA Entry & Routing

The frontend is a Vite-built SPA using `react-router-dom` for client-side routing.

**Entry points** (`src/spa/`):

- `entry.web.tsx` — Web browser (desktop layout)
- `entry.mobile.tsx` — Mobile browser
- `entry.desktop.tsx` — Electron desktop app
- `entry.popup.tsx` — Popup windows (Electron)

**Router configs** (`src/spa/router/`):

- `desktopRouter.config.tsx` — Web + desktop routes
- `desktopRouter.config.desktop.tsx` — Electron-specific routes (must stay in sync)
- `mobileRouter.config.tsx` — Mobile routes
- `popupRouter.config.tsx` — Popup routes
- `webRouter.config.ts` — Web-specific wrapper

**Route segments** (`src/routes/`):

```
src/routes/
├── (main)/          # Primary desktop pages (agent, home, settings, admin, etc.)
├── (mobile)/        # Mobile-specific pages
├── (auth)/          # Authentication pages (signin, signup, reset-password, etc.)
└── onboarding/      # Onboarding flow
```

> **Convention:** Route files are thin shells that import from `src/features/`. No business logic in route files.

### Feature Domains (`src/features/`)

Business components organized by domain (\~75 domains, \~1,200 items):

| Category             | Key Domains                                                         | Items |
| -------------------- | ------------------------------------------------------------------- | ----- |
| **Core Chat**        | `Conversation/`, `ChatInput/`, `ChatMiniMap/`, `SuggestQuestions/`  | \~475 |
| **Agent System**     | `AgentBuilder/`, `AgentHome/`, `AgentSetting/`, `AgentProfileCard/` | \~53  |
| **Tasks**            | `AgentTasks/`, `AgentTaskManager/`, `AgentTaskList/`                | \~75  |
| **Skills & Plugins** | `SkillStore/`, `MCP/`, `MCPPluginDetail/`, `PluginDevModal/`        | \~105 |
| **Portal**           | `Portal/` (artifacts, threads, documents, file preview, notebook)   | \~60  |
| **Pages & Docs**     | `Pages/`, `PageEditor/`, `EditorCanvas/`, `DocumentModal/`          | \~88  |
| **Resources**        | `ResourceManager/`, `FileViewer/`, `FileTree/`, `LibraryModal/`     | \~113 |
| **Models**           | `ModelSwitchPanel/`, `ModelParamsControl/`, `OllamaSetupGuide/`     | \~66  |
| **Navigation**       | `NavPanel/`, `CommandMenu/`, `MobileTabBar/`, `HotkeyHelperPanel/`  | \~43  |
| **User & Auth**      | `User/`, `Admin/`, `ProfileEditor/`, `AuthCard/`, `Setting/`        | \~30  |
| **Sharing**          | `ShareModal/`, `SharePopover/`, `DataImporter/`                     | \~36  |
| **Misc**             | `DailyBrief/`, `Onboarding/`, `DevPanel/`, `PWAInstall/`            | \~70  |

### State Management (`src/store/`)

Zustand stores follow a **slice pattern** — each store is split into action slices for modularity.

| Store           | Responsibility                                                    |
| --------------- | ----------------------------------------------------------------- |
| `chat/`         | Active conversation, messages, AI chat execution, agent executors |
| `agent/`        | Agent config, metadata, CRUD                                      |
| `agentGroup/`   | Agent group management                                            |
| `session/`      | Session list, active session                                      |
| `tool/`         | Plugin/tool state, MCP integration                                |
| `file/`         | File management, uploads                                          |
| `user/`         | User profile, preferences, settings                               |
| `userMemory/`   | User memory system                                                |
| `global/`       | App-wide state (theme, command menu, layout)                      |
| `serverConfig/` | Server-provided config & feature flags                            |
| `home/`         | Home page state                                                   |
| `discover/`     | Marketplace/discover state                                        |
| `page/`         | Pages/notes state                                                 |
| `document/`     | Document editor state                                             |
| `task/`         | Task management state                                             |
| `aiInfra/`      | AI provider & model infrastructure                                |
| ...             | (27 stores total)                                                 |

### Client Services (`src/services/`)

Services provide the data-fetching layer between stores and the backend. Each service maps to a backend domain:

```
Store ──→ Service ──→ TRPC Client ──→ Hono Server ──→ TRPC Router ──→ Server Service
```

Services handle auth headers (`_auth.ts`), URL construction (`_url.ts`), and request headers (`_header.ts`).

---

## Backend Architecture

### Hono Server (`src/hono-server/`)

The server is a Hono application bundled by Vite into a single `server.mjs` file.

**Route mounting** (`src/hono-server/index.ts`):

| Route              | Handler               | Description                            |
| ------------------ | --------------------- | -------------------------------------- |
| `/api/auth/*`      | `auth.ts`             | better-auth authentication             |
| `/trpc/lambda/*`   | `trpc.ts`             | Main TRPC router (57+ procedures)      |
| `/trpc/async/*`    | `trpc.ts`             | Async/long-running TRPC procedures     |
| `/trpc/mobile/*`   | `trpc.ts`             | Mobile-optimized TRPC procedures       |
| `/trpc/tools/*`    | `trpc.ts`             | Tool execution TRPC procedures         |
| `/api/agent/*`     | `routes/agent.ts`     | Agent streaming, gateway, tool results |
| `/api/workflows/*` | `routes/workflows.ts` | Agent eval workflows                   |
| `/api/webhooks/*`  | `routes/webhooks.ts`  | External webhooks                      |
| `/webapi/*`        | `routes/webapi.ts`    | Web API (revalidation, etc.)           |
| `/market/*`        | `routes/market.ts`    | Marketplace API                        |
| `/oidc/*`          | `routes/oidc.ts`      | OpenID Connect                         |
| `/*`               | `spa.ts`              | SPA catch-all (serves HTML template)   |

### TRPC Routers (`src/server/routers/`)

Four TRPC router groups:

| Router     | Path           | Purpose                                                |
| ---------- | -------------- | ------------------------------------------------------ |
| **Lambda** | `/trpc/lambda` | Primary API — 57+ sub-routers covering all domains     |
| **Async**  | `/trpc/async`  | Long-running operations (agent eval, batch generation) |
| **Mobile** | `/trpc/mobile` | Mobile-optimized endpoints                             |
| **Tools**  | `/trpc/tools`  | Tool call execution                                    |

**Lambda router sub-routers** include: `agent`, `message`, `session`, `topic`, `file`, `knowledge`, `plugin`, `user`, `admin`, `aiModel`, `aiProvider`, `task`, `document`, `notebook`, `search`, `generation`, `share`, `upload`, `usage`, `video`, `comfyui`, and 35+ more.

### Server Services (`src/server/services/`)

Business logic layer (\~48 service domains, \~567 items):

| Service          | Responsibility                                             |
| ---------------- | ---------------------------------------------------------- |
| `agentRuntime/`  | Agent execution orchestration                              |
| `agentSignal/`   | Agent Signal pipeline (event-driven agent work)            |
| `bot/`           | Bot platform integrations (Discord, Slack, Telegram, etc.) |
| `toolExecution/` | Tool call routing and execution                            |
| `search/`        | Web search integration                                     |
| `generation/`    | Content generation                                         |
| `mcp/`           | Model Context Protocol services                            |
| `memory/`        | User memory management                                     |
| `file/`          | File operations & S3 interactions                          |
| `email/`         | Email service (SMTP, Resend)                               |
| `gateway/`       | Agent gateway management                                   |
| `comfyui/`       | ComfyUI workflow integration                               |
| ...              |                                                            |

### Server Modules (`src/server/modules/`)

Infrastructure modules providing cross-cutting capabilities:

| Module              | Responsibility                    |
| ------------------- | --------------------------------- |
| `AgentRuntime/`     | Multi-provider AI model execution |
| `ModelRuntime/`     | Model invocation with tracing     |
| `S3/`               | S3 storage abstraction            |
| `KeyVaultsEncrypt/` | Encryption for API key storage    |
| `PluginStore/`      | Plugin marketplace access         |
| `ContentChunk/`     | RAG content chunking              |
| `GitHub/`           | GitHub API integration            |
| `Mecha/`            | Agent orchestration engine        |

---

## Database Layer

### ORM & Schema

- **ORM:** Drizzle ORM with PostgreSQL
- **Schema location:** `packages/database/src/schemas/` (28 schema files)
- **Migrations:** `packages/database/migrations/`
- **Config:** `drizzle.config.ts` at project root

### Schema Domains

| Schema File         | Tables                                 |
| ------------------- | -------------------------------------- |
| `agent.ts`          | Agents, agent config                   |
| `session.ts`        | Chat sessions                          |
| `message.ts`        | Messages, message plugins, message TTS |
| `topic.ts`          | Topics, topic relations                |
| `file.ts`           | Files, file chunks, embeddings         |
| `user.ts`           | Users, user settings                   |
| `task.ts`           | Tasks, task runs, task templates       |
| `generation.ts`     | AI-generated content                   |
| `rag.ts`            | RAG embeddings, chunks                 |
| `agentEvals.ts`     | Agent evaluation datasets & runs       |
| `agentDocuments.ts` | Agent-attached documents               |
| `agentSkill.ts`     | Agent skills                           |
| `aiInfra.ts`        | AI providers, models                   |
| `notification.ts`   | Notifications                          |
| `oidc.ts`           | OIDC clients, grants, tokens           |
| `betterAuth.ts`     | Auth sessions, accounts, verification  |
| `rbac.ts`           | Role-based access control              |
| `chatGroup.ts`      | Multi-agent chat groups                |
| ...                 |                                        |

### Database Architecture

```
packages/database/src/
├── schemas/        # Drizzle table definitions (28 files)
├── models/         # Data access models (143 items)
├── repositories/   # Repository pattern abstractions (40 items)
├── core/           # DB connection & transaction management
├── server/         # Server-specific DB utilities
└── types/          # Database type definitions
```

---

## Data Flow

### Client → Server Request Flow

```
React Component
    │
    ▼
Zustand Store (action)
    │
    ▼
Client Service (src/services/*.ts)
    │
    ▼
TRPC Client (type-safe RPC call)
    │
    ▼ HTTP
Hono Server
    │
    ▼
TRPC Router (src/server/routers/)
    │
    ▼
Server Service (src/server/services/)
    │
    ▼
Database Model (packages/database/src/models/)
    │
    ▼
PostgreSQL
```

### SPA Serving Flow

```
Browser Request (GET /any-path)
    │
    ▼
Hono Server (catch-all)
    │
    ▼
spa.ts → serveSPA()
    ├── Detect mobile via User-Agent
    ├── Detect locale via Accept-Language
    ├── Inject __SERVER_CONFIG__ (feature flags, analytics, global config)
    ├── Inject SEO meta tags
    └── Return HTML template (from dist/web/ or dist/mobile/)
    │
    ▼
Browser loads SPA → React Router handles client-side routing
```

### Agent Execution Flow

```
User Message
    │
    ▼
Chat Store → createAgentExecutors
    │
    ▼
Client Service → POST /api/agent/stream (or /api/agent/run)
    │
    ▼
Hono Handler → Agent Route
    │
    ▼
AgentRuntime Module (multi-provider)
    ├── Context Engine (assembles prompt + history + RAG context)
    ├── Model Runtime (routes to provider: OpenAI, Anthropic, etc.)
    ├── Tool Execution (function calls → tool results)
    └── Tracing (observability)
    │
    ▼
SSE Stream → Client (real-time message rendering)
```

---

## Build System

### Build Targets

| Command                    | Output                        | Description             |
| -------------------------- | ----------------------------- | ----------------------- |
| `bun run build:spa`        | `dist/web/`                   | Vite SPA build (web)    |
| `bun run build:spa:mobile` | `dist/mobile/`                | Vite SPA build (mobile) |
| `bun run build:hono`       | `dist/hono-server/server.mjs` | Hono server bundle      |
| `bun run build`            | Both above                    | Full production build   |
| `bun run build:docker`     | All + sitemap                 | Docker-optimized build  |

### Vite Configuration

**SPA build** (`vite.config.ts`):

- Entry: `index.html` (web) / `index.mobile.html` (mobile)
- Shared renderer plugins for React, i18n, PWA
- Code splitting via Rolldown

**Server build** (`vite.config.hono.ts`):

- Entry: `src/hono-server/index.ts`
- Output: Single `server.mjs` (ESM, `inlineDynamicImports: true`)
- Target: Node.js 20+
- Heavy deps externalized (hono, drizzle, postgres, better-auth, sharp, etc.)
- All other deps bundled (`ssr.noExternal: true`)

### Development

```bash
# Full-stack dev (Hono + Vite concurrently)
bun run dev

# SPA only (frontend dev against production backend)
bun run dev:spa

# Server only
bun run dev:hono

# Dev infrastructure (Postgres, Redis, S3, SearXNG)
bun run dev:docker
```

---

## Deployment

### Docker

The production Docker image is built from a multi-stage `Dockerfile`:

```
Stage 1: base         → Node.js slim + proxychains + native libs
Stage 2: builder      → Install deps, build SPA + Hono
Stage 3: app          → Copy artifacts to busybox
Stage 4: scratch      → Minimal production image
```

**Artifacts copied:**

- `dist/hono-server/server.mjs` — Server bundle
- `dist/web/` — Web SPA assets
- `dist/mobile/` — Mobile SPA assets
- `packages/database/migrations/` — DB migrations
- `node_modules/pg`, `node_modules/drizzle-orm` — Runtime DB deps

**Entry point:** `node /app/startServer.js` → runs migrations, then starts `server.mjs`

**Port:** 3210 (default)

### Environment Variables

The application is extensively configurable via environment variables:

| Category         | Examples                                                     |
| ---------------- | ------------------------------------------------------------ |
| **General**      | `APP_URL`, `FEATURE_FLAGS`, `PROXY_URL`                      |
| **Database**     | `DATABASE_URL`, `KEY_VAULTS_SECRET`                          |
| **Auth**         | `AUTH_SECRET`, `AUTH_SSO_PROVIDERS`, `AUTH_GOOGLE_ID`, etc.  |
| **Redis**        | `REDIS_URL`, `REDIS_PREFIX`                                  |
| **Email**        | `SMTP_HOST`, `RESEND_API_KEY`                                |
| **S3**           | `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_BUCKET`               |
| **AI Providers** | 50+ provider-specific keys (OpenAI, Anthropic, Google, etc.) |
| **Features**     | `ENABLED_ARTIFACTS`, `ENABLED_MCP`, `ENABLED_UPLOAD`, etc.   |
| **Analytics**    | Google Analytics, Plausible, Umami, Clarity, PostHog         |

---

## Feature Flags

### Configuration

All feature flags are controlled via a single `FEATURE_FLAGS` environment variable:

```bash
FEATURE_FLAGS="+enterprise_mode,+commercial_hide_github,-changelog,-market"
```

Syntax: `+flag_name` enables, `-flag_name` disables. Comma-separated.

### Available Flags

| Flag                     | Default  | Description                                        |
| ------------------------ | -------- | -------------------------------------------------- |
| `enterprise_mode`        | off      | Meta-flag: disables consumer features globally     |
| `market`                 | off      | Marketplace/discover tab                           |
| `knowledge_base`         | on       | Knowledge base & RAG                               |
| `agent_task`             | dev-only | Agent tasks system                                 |
| `admin_panel`            | dev-only | Admin panel                                        |
| `bot_channels`           | off      | Bot platform integrations                          |
| `resources`              | off      | Resource manager                                   |
| `ai_image`               | off      | AI image generation                                |
| `speech_to_text`         | on       | STT in chat input                                  |
| `edit_agent`             | on       | Agent editing capability                           |
| `welcome_suggest`        | on       | Welcome suggestions                                |
| `changelog`              | on       | Changelog display                                  |
| `check_updates`          | on       | Update checker                                     |
| `rag_eval`               | off      | RAG evaluation tools                               |
| `commercial_hide_github` | off      | Hide GitHub links (commercial license required)    |
| `commercial_hide_docs`   | off      | Hide docs/help links (commercial license required) |

### Per-User Targeting

Flags support user-ID-based targeting for gradual rollout:

```typescript
// Boolean: global on/off
{
  market: true;
}

// Array: enabled only for specific users
{
  market: ['user-id-1', 'user-id-2'];
}
```

### Enterprise Mode

When `enterprise_mode` is enabled, these features are force-disabled:

- Provider settings, API key inputs, proxy URL inputs
- AI image generation, changelog, update checker
- Cloud promotion, marketplace, RAG eval
- GitHub links are force-hidden

---

## Packages

### Core Packages

| Package                       | Description                                       |
| ----------------------------- | ------------------------------------------------- |
| `@lobechat/database`          | Drizzle schemas, models, repositories, migrations |
| `@lobechat/agent-runtime`     | Agent execution runtime                           |
| `@lobechat/context-engine`    | LLM context assembly (history, RAG, tools)        |
| `@lobechat/model-runtime`     | Multi-provider model abstraction                  |
| `@lobechat/model-bank`        | Model metadata, capabilities, pricing             |
| `@lobechat/conversation-flow` | Conversation flow management                      |
| `@lobechat/types`             | Shared TypeScript types                           |
| `@lobechat/const`             | Shared constants                                  |
| `@lobechat/utils`             | Shared utilities                                  |
| `@lobechat/prompts`           | System prompt templates                           |

### Tool Packages (\~25)

Each builtin tool is a self-contained package:

| Package                       | Tool                                |
| ----------------------------- | ----------------------------------- |
| `builtin-tool-web-browsing`   | Web browsing & scraping             |
| `builtin-tool-knowledge-base` | Knowledge base queries              |
| `builtin-tool-cloud-sandbox`  | Cloud code execution                |
| `builtin-tool-memory`         | User memory management              |
| `builtin-tool-calculator`     | Calculations                        |
| `builtin-tool-claude-code`    | Claude Code integration             |
| `builtin-tool-local-system`   | Local file system access            |
| `builtin-tool-agent-builder`  | Agent creation                      |
| `builtin-tool-notebook`       | Note-taking                         |
| `builtin-tool-gtd`            | Getting Things Done task management |
| ...                           |                                     |

### Python Backend Platform Adapters

| Python service path                                | Platform    |
| -------------------------------------------------- | ----------- |
| `python-backend/app/services/bot/platforms/feishu` | Feishu/Lark |
| `python-backend/app/services/bot/platforms/qq`     | QQ          |
| `python-backend/app/services/bot/platforms/wechat` | WeChat      |
| `python-backend/app/services/bot/platforms/line`   | LINE        |

### Infrastructure Packages

| Package                          | Description                                  |
| -------------------------------- | -------------------------------------------- |
| `@lobechat/agent-signal`         | Event-driven agent pipelines                 |
| `@lobechat/agent-tracing`        | Agent execution tracing & debugging          |
| `@lobechat/observability-otel`   | OpenTelemetry integration                    |
| `@lobechat/ssrf-safe-fetch`      | SSRF-protected HTTP client                   |
| `@lobechat/file-loaders`         | Document parsing (PDF, DOCX, etc.)           |
| `@lobechat/web-crawler`          | Web content extraction                       |
| `@lobechat/python-interpreter`   | Python code execution (Pyodide)              |
| `@lobechat/eval-rubric`          | Agent evaluation rubrics                     |
| `@lobechat/heterogeneous-agents` | External agent adapters (Claude Code, Codex) |

---

## Key Design Decisions

### 1. Routes vs Features Split

Route files (`src/routes/`) are **thin shells** — they only compose layout and import from `src/features/`. All business logic and heavy UI lives in feature domains. This keeps the routing layer declarative and the business logic reusable.

### 2. Zustand Slice Pattern

Each Zustand store is split into **action slices** for modularity. Slices are composed in the store's `initialState` and `createStore` — this avoids monolithic store files while maintaining a single store instance per domain.

### 3. Service Layer Abstraction

Client services (`src/services/`) abstract all data fetching. Stores never call TRPC directly — they go through services. This allows swapping backends (e.g., local IndexedDB vs. server) without touching store code.

### 4. Server Config Injection

Server configuration (feature flags, analytics config, global settings) is injected into the SPA HTML template at serve time via `window.__SERVER_CONFIG__`. This avoids client-side API calls for boot-critical config while keeping the SPA fully static/cacheable.

### 5. Single-File Server Bundle

The Hono server is bundled into a single `server.mjs` file using Vite with `inlineDynamicImports: true`. This simplifies deployment (no `node_modules` tree-shaking issues) while keeping heavy native deps external.

### 6. Monorepo Package Isolation

Tools, adapters, and infrastructure are isolated into \~72 packages under `packages/`. Each package has its own `package.json`, can be tested independently, and has clear dependency boundaries. This enables parallel development and potential future extraction.

---

## Licensing

- **Ethos Community License** (based on Apache 2.0)
- Free for commercial use as-is (no source modification)
- Commercial license required for derivative works that are distributed
- Enterprise/commercial branding flags (`commercial_hide_github`, `commercial_hide_docs`) require a commercial license
- Contact: <hello@lobehub.com>
