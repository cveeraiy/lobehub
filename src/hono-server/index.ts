import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';

import workflowsApp from '@/server/workflows-hono';

import { pendingTasks } from './afterResponseRegistry';
import authApp from './auth';
import agentRoutes from './routes/agent';
import apiRoutes from './routes/api';
import marketRoutes from './routes/market';
import oidcRoutes from './routes/oidc';
import webapiRoutes from './routes/webapi';
import webhookRoutes from './routes/webhooks';
import workflowRoutes from './routes/workflows';
import spaApp from './spa';
import trpcApp from './trpc';

const app = new Hono();

// ============ Global Error Handler ============ //
app.onError((err, c) => {
  console.error('[Hono] Unhandled error:', err);
  if (c.res.headers.get('content-type')?.includes('text/event-stream')) {
    // SSE stream — nothing useful we can send
    return c.text('', 500);
  }
  return c.json(
    {
      error: process.env.NODE_ENV === 'development' ? err.message : 'Internal Server Error',
      status: 500,
    },
    500,
  );
});

// ============ Global Middleware ============ //
app.use('*', logger());
app.use('*', cors());

// ============ Auth (better-auth) ============ //
app.route('/', authApp);

// ============ TRPC Routers ============ //
app.route('/', trpcApp);

// ============ Workflows (already Hono) ============ //
app.route('/', workflowsApp);

// ============ Web API Routes ============ //
app.route('/', webapiRoutes);

// ============ API Routes ============ //
app.route('/', apiRoutes);

// ============ Agent Routes ============ //
app.route('/', agentRoutes);

// ============ Webhook Routes ============ //
app.route('/', webhookRoutes);

// ============ Agent Eval Workflow Routes ============ //
app.route('/', workflowRoutes);

// ============ Market Routes ============ //
app.route('/', marketRoutes);

// ============ OIDC Routes ============ //
app.route('/', oidcRoutes);

// ============ Static Assets ============ //
if (process.env.NODE_ENV !== 'development') {
  // Serve Vite-built SPA assets (JS, CSS, images) from dist/desktop and dist/mobile
  app.use('/assets/*', serveStatic({ root: './dist/desktop' }));
  // Serve legacy /_spa/ assets if any remain
  app.use('/_spa/*', serveStatic({ root: './public' }));
  // Serve other static files from dist/desktop (favicon, manifest, etc.)
  app.use('/favicon.ico', serveStatic({ root: './dist/desktop', path: '/favicon.ico' }));
}

// ============ API 404 — catch unmatched /api, /trpc, /webapi, /oidc, /market ============ //
// Must be BEFORE the SPA catch-all so mistyped API paths return JSON 404
app.all('/api/*', (c) => c.json({ error: 'Not Found', path: c.req.path }, 404));
app.all('/trpc/*', (c) => c.json({ error: 'Not Found', path: c.req.path }, 404));
app.all('/webapi/*', (c) => c.json({ error: 'Not Found', path: c.req.path }, 404));
app.all('/oidc/*', (c) => c.json({ error: 'Not Found', path: c.req.path }, 404));
app.all('/market/*', (c) => c.json({ error: 'Not Found', path: c.req.path }, 404));

// ============ SPA Catch-All ============ //
app.route('/', spaApp);

// ============ Start Server ============ //
const port = Number(process.env.PORT) || 3010;

const server = serve(
  {
    fetch: app.fetch,
    port,
  },
  (info) => {
    console.info(
      [
        '',
        `  🔥 Hono server running at http://localhost:${info.port}`,
        '',
        '  TRPC endpoints:',
        '    - /trpc/lambda',
        '    - /trpc/async',
        '    - /trpc/mobile',
        '    - /trpc/tools',
        '  Auth: /api/auth/*',
        '  Workflows: /api/workflows/*',
        '  WebAPI: /webapi/*',
        '  API: /api/*',
        '  Agent: /api/agent/*',
        '  Webhooks: /api/webhooks/*',
        '  Agent Eval: /api/workflows/agent-eval-run/*',
        '  Market: /market/*',
        '  OIDC: /oidc/*',
        '  SPA: /*',
        '',
      ].join('\n'),
    );
  },
);

// ============ Graceful Shutdown ============ //
const shutdown = async (signal: string) => {
  console.info(`\n  ⏳ Received ${signal}, shutting down gracefully...`);
  server.close();

  // Wait for in-flight afterResponse tasks (max 5s)
  const deadline = Date.now() + 5000;
  while (pendingTasks.size > 0 && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 100));
  }
  if (pendingTasks.size > 0) {
    console.warn(`  ⚠️ ${pendingTasks.size} deferred task(s) still pending, exiting anyway.`);
  }

  console.info('  ✅ Server stopped.');
  process.exit(0);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

export default app;
