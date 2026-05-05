# LobeHub — Setup Guide

LobeHub runs on a **Hono** server with a **Vite** SPA frontend. This guide covers both local development and production deployment.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Hono Server                       │
│  (:3010 dev / :3210 prod)                           │
│                                                      │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │  TRPC (4x)   │  │  Auth      │  │  WebAPI     │  │
│  │  /trpc/*     │  │  /api/auth │  │  /webapi/*  │  │
│  └──────────────┘  └────────────┘  └─────────────┘  │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │  Agent       │  │  OIDC      │  │  Webhooks   │  │
│  │  /api/agent  │  │  /oidc/*   │  │  /api/wh/*  │  │
│  └──────────────┘  └────────────┘  └─────────────┘  │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │  Workflows   │  │  Market    │  │  SPA (*)    │  │
│  │  /api/wf/*   │  │  /market/* │  │  catch-all  │  │
│  └──────────────┘  └────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────┘
         ▲                              ▲
         │ API calls                    │ HTML + assets
         │                              │
┌────────┴──────────────────────────────┴──────────┐
│              Vite SPA (React)                     │
│  Desktop: dist/desktop    Mobile: dist/mobile     │
│  Dev server: localhost:9876                       │
└──────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool       | Version | Purpose                    |
| ---------- | ------- | -------------------------- |
| Node.js    | >= 20   | Runtime                    |
| pnpm       | >= 9    | Package management         |
| bun        | >= 1    | Script runner              |
| PostgreSQL | >= 14   | Database                   |
| Redis      | >= 6    | Session / cache (optional) |

---

## Local Development

### 1. Clone & install dependencies

```bash
git clone https://github.com/lobehub/lobehub.git
cd lobehub
pnpm install
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with at minimum:

```env
# Database
DATABASE_URL=postgres://postgres:password@localhost:5432/lobehub
DATABASE_DRIVER=node

# Auth
AUTH_SECRET=your-secret-here
KEY_VAULTS_SECRET=your-vault-secret

# Optional: Enable mock dev user (skip auth in dev)
ENABLE_MOCK_DEV_USER=1
MOCK_DEV_USER_ID=DEV_USER
```

### 3. Run database migrations

```bash
bun run db:migrate
```

### 4. Start development servers

**Full-stack (recommended):**

```bash
bun run dev
```

This starts both:

- **Vite SPA dev server** on `http://localhost:9876` (HMR enabled)
- **Hono API server** on `http://localhost:3010` (proxies SPA from Vite)

Open **<http://localhost:3010>** to use the app.

**Individual servers (advanced):**

```bash
# Terminal 1: SPA dev server only
bun run dev:spa

# Terminal 2: Hono server only (requires dev:spa to be running)
bun run dev:hono
```

**Debug Proxy (develop against production backend):**

After `dev:spa` starts, the terminal prints a Debug Proxy URL:

```
Debug Proxy: https://app.lobehub.com/_dangerous_local_dev_proxy?debug-host=http%3A%2F%2Flocalhost%3A9876
```

Open this URL to develop the SPA locally with the production backend.

### 5. Run tests

```bash
# Run a specific test file (NEVER run `bun run test` — takes ~10 min)
bunx vitest run --silent='passed-only' 'path/to/file.test.ts'

# Database package tests
cd packages/database && bunx vitest run --silent='passed-only' 'path/to/file.test.ts'

# Type check
bun run type-check
```

---

## Production Build

### Option A: Direct (bare metal / VM)

```bash
# 1. Install dependencies
pnpm install

# 2. Build SPA + Hono server
bun run build

# This produces:
#   dist/desktop/       — Desktop SPA bundle
#   dist/mobile/        — Mobile SPA bundle
#   dist/hono-server/   — server.mjs (Hono server bundle)

# 3. Start the server
NODE_ENV=production node --env-file=.env dist/hono-server/server.mjs
```

The server listens on `PORT` (default `3210`).

### Option B: Docker

```bash
# Build the image
docker build -t lobehub .

# Run with environment variables
docker run -d \
  -p 3210:3210 \
  -e DATABASE_URL=postgres://user:pass@host:5432/lobehub \
  -e DATABASE_DRIVER=node \
  -e AUTH_SECRET=your-secret \
  -e KEY_VAULTS_SECRET=your-vault-secret \
  lobehub
```

**Docker Compose** (with PostgreSQL + Redis):

```yaml
version: '3.8'
services:
  lobehub:
    build: .
    ports:
      - '3210:3210'
    environment:
      DATABASE_URL: postgres://postgres:password@db:5432/lobehub
      DATABASE_DRIVER: node
      AUTH_SECRET: change-me
      KEY_VAULTS_SECRET: change-me
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: password
      POSTGRES_DB: lobehub
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
```

### Option C: Dev Docker services only

```bash
# Start PostgreSQL, Redis, RustFS, SearXNG
bun run dev:docker

# Reset everything (destroy volumes)
bun run dev:docker:reset

# Stop
bun run dev:docker:down
```

---

## Available Scripts

| Script                     | Description                                       |
| -------------------------- | ------------------------------------------------- |
| `bun run dev`              | Full-stack dev (Hono + Vite SPA concurrently)     |
| `bun run dev:spa`          | Vite SPA dev server only (port 9876)              |
| `bun run dev:hono`         | Build & run Hono server in dev mode (port 3010)   |
| `bun run build`            | Production build (SPA + Hono)                     |
| `bun run build:hono`       | Build Hono server bundle only                     |
| `bun run build:spa`        | Build desktop SPA only                            |
| `bun run build:spa:mobile` | Build mobile SPA only                             |
| `bun run build:docker`     | Full Docker build (SPA + mobile + Hono + sitemap) |
| `bun run db:migrate`       | Run database migrations                           |
| `bun run db:generate`      | Generate new migration files                      |
| `bun run db:studio`        | Open Drizzle Studio GUI                           |

---

## Project Structure

```
lobehub/
├── src/
│   ├── hono-server/           # Hono server entry + routes
│   │   ├── index.ts           # Main app, middleware, startup
│   │   ├── spa.ts             # SPA template handler
│   │   ├── auth.ts            # better-auth mount
│   │   ├── trpc.ts            # TRPC endpoint handlers
│   │   ├── middleware/auth.ts  # Auth middleware
│   │   └── routes/            # Route modules (agent, webapi, oidc, etc.)
│   ├── spa/                   # SPA entry points + React Router config
│   ├── routes/                # SPA page segments
│   ├── features/              # Business logic components
│   ├── store/                 # Zustand stores
│   ├── server/                # Server services, routers, global config
│   ├── handlers/              # HTTP handler functions (migrated from Next.js)
│   └── libs/                  # Shared libraries (trpc, oidc, etc.)
├── packages/                  # Shared packages (@lobechat/*)
│   ├── database/              # Drizzle schemas, models, repositories
│   ├── agent-runtime/         # Agent runtime
│   └── utils/                 # Server/client utilities
├── dist/                      # Build output
│   ├── desktop/               # Vite SPA build (desktop)
│   ├── mobile/                # Vite SPA build (mobile)
│   └── hono-server/           # Bundled server (server.mjs)
├── vite.config.ts             # SPA Vite config
├── vite.config.hono.ts        # Hono server Vite/Rolldown config
├── Dockerfile                 # Multi-stage production image
└── package.json
```

---

## Environment Variables

### Required

| Variable            | Description                            |
| ------------------- | -------------------------------------- |
| `DATABASE_URL`      | PostgreSQL connection string           |
| `DATABASE_DRIVER`   | `node` (for Node.js pg driver)         |
| `AUTH_SECRET`       | Secret for better-auth session signing |
| `KEY_VAULTS_SECRET` | Encryption key for API key vaults      |

### Optional — Auth

| Variable                                      | Description                       |
| --------------------------------------------- | --------------------------------- |
| `AUTH_SSO_PROVIDERS`                          | Comma-separated SSO provider list |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET`       | Google OAuth credentials          |
| `AUTH_GITHUB_ID` / `AUTH_GITHUB_SECRET`       | GitHub OAuth credentials          |
| `AUTH_MICROSOFT_ID` / `AUTH_MICROSOFT_SECRET` | Microsoft OAuth credentials       |
| `AUTH_TRUSTED_ORIGINS`                        | Trusted CORS origins for auth     |

### Optional — S3 Storage

| Variable               | Description      |
| ---------------------- | ---------------- |
| `S3_ACCESS_KEY_ID`     | S3 access key    |
| `S3_SECRET_ACCESS_KEY` | S3 secret key    |
| `S3_ENDPOINT`          | S3 endpoint URL  |
| `S3_BUCKET`            | S3 bucket name   |
| `S3_DOMAIN`            | Public S3 domain |

### Optional — Redis

| Variable       | Description          |
| -------------- | -------------------- |
| `REDIS_URL`    | Redis connection URL |
| `REDIS_PREFIX` | Key prefix           |

### Optional — Analytics

| Variable                          | Description       |
| --------------------------------- | ----------------- |
| `ENABLE_GOOGLE_ANALYTICS`         | Enable GA         |
| `GOOGLE_ANALYTICS_MEASUREMENT_ID` | GA measurement ID |
| `ENABLED_PLAUSIBLE_ANALYTICS`     | Enable Plausible  |
| `PLAUSIBLE_DOMAIN`                | Plausible domain  |
| `ENABLED_UMAMI_ANALYTICS`         | Enable Umami      |
| `UMAMI_WEBSITE_ID`                | Umami website ID  |

### Optional — Proxy

| Variable           | Description                                |
| ------------------ | ------------------------------------------ |
| `PROXY_URL`        | HTTP/SOCKS proxy URL for outbound requests |
| `ENABLE_PROXY_DNS` | Route DNS through proxy (`1` to enable)    |

---

## Server Architecture Notes

- **Hono** handles all HTTP: API routes, TRPC, auth, OIDC, webhooks, and SPA serving
- **Vite** builds the SPA (desktop + mobile); in dev mode, Hono proxies the Vite dev server
- **TRPC** provides type-safe client-server communication via 4 routers (lambda, async, mobile, tools)
- **better-auth** handles authentication (sessions, OAuth, magic links)
- **OIDC Provider** enables CLI and third-party auth via OpenID Connect
- **Graceful shutdown** waits for in-flight `afterResponse` tasks before exiting
- **Global error handler** catches unhandled exceptions and returns structured JSON errors
- **API 404s** return JSON (not SPA HTML) for mistyped `/api/*`, `/trpc/*`, `/webapi/*`, `/oidc/*`, `/market/*` paths
