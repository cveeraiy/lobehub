import { Hono } from 'hono';

import { POST as agentGatewayCallback } from '@/handlers/api/agent/gateway/callback/route';
import { GET as agentGateway } from '@/handlers/api/agent/gateway/route';
import { POST as agentGatewayStart } from '@/handlers/api/agent/gateway/start/route';
import { POST as agentExec } from '@/handlers/api/agent/route';
import { GET as agentRunHealth, POST as agentRun } from '@/handlers/api/agent/run/route';
import { GET as agentStream } from '@/handlers/api/agent/stream/route';
import { POST as agentToolResult } from '@/handlers/api/agent/tool-result/route';
import { POST as platformWebhook } from '@/handlers/api/agent/webhooks/[platform]/[[...appId]]/route';
import { POST as botCallback } from '@/handlers/api/agent/webhooks/bot-callback/route';

const agent = new Hono();

// ============ Agent Execution ============ //
agent.post('/api/agent', (c) => agentExec(c.req.raw));

// ============ Agent Step Run ============ //
agent.post('/api/agent/run', (c) => agentRun(c.req.raw));
agent.get('/api/agent/run', () => agentRunHealth() as any);

// ============ Agent SSE Stream ============ //
agent.get('/api/agent/stream', (c) => agentStream(c.req.raw));

// ============ Agent Gateway ============ //
agent.get('/api/agent/gateway', (c) => agentGateway(c.req.raw));
agent.post('/api/agent/gateway/start', (c) => agentGatewayStart(c.req.raw));
agent.post('/api/agent/gateway/callback', (c) => agentGatewayCallback(c.req.raw));

// ============ Agent Tool Result ============ //
agent.post('/api/agent/tool-result', (c) => agentToolResult(c.req.raw));

// ============ Agent Bot Callback ============ //
agent.post('/api/agent/webhooks/bot-callback', (c) => botCallback(c.req.raw));

// ============ Platform Webhooks ============ //
// Handles both /api/agent/webhooks/:platform and /api/agent/webhooks/:platform/:appId
agent.post('/api/agent/webhooks/:platform/:appId?', (c) => {
  const platform = c.req.param('platform');
  const appId = c.req.param('appId');
  // The original handler expects Next.js-style { params: Promise<...> }
  return platformWebhook(c.req.raw, {
    params: Promise.resolve({ appId: appId ? [appId] : undefined, platform }),
  });
});

export default agent;
