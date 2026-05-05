import { Hono } from 'hono';

import { MarketService } from '@/server/services/market';

import { jsonError } from './helpers';

const agent = new Hono();

agent.all('/market/agent/*', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;

  const fullPath = c.req.path.replace('/market/agent/', '').replace('/market/agent', '');
  const segments = fullPath ? fullPath.split('/').map(decodeURIComponent) : [];

  if (segments.length === 0) return jsonError(c, 'not_found', 'Missing agent action.', 404);

  const [action, ...rest] = segments;

  // POST-only actions
  if (action === 'create') {
    if (c.req.method !== 'POST') return c.json({ error: 'method_not_allowed' }, 405);
    try {
      return c.json(await sdk.agents.createAgent(await c.req.json()));
    } catch (e: any) {
      return jsonError(c, 'create_agent_failed', e?.message || 'Unknown error', 500);
    }
  }

  if (action === 'own') {
    if (c.req.method !== 'GET') return c.json({ error: 'method_not_allowed' }, 405);
    try {
      const url = new URL(c.req.url);
      const page = url.searchParams.get('page');
      const pageSize = url.searchParams.get('pageSize');
      return c.json(
        await sdk.agents.getOwnAgents({
          page: page ? parseInt(page, 10) : undefined,
          pageSize: pageSize ? parseInt(pageSize, 10) : undefined,
        }),
      );
    } catch (e: any) {
      return jsonError(c, 'get_own_agents_failed', e?.message || 'Unknown error', 500);
    }
  }

  if (action === 'versions' && rest.length === 1 && rest[0] === 'create') {
    if (c.req.method !== 'POST') return c.json({ error: 'method_not_allowed' }, 405);
    try {
      const payload = await c.req.json();
      if (!payload?.identifier)
        return jsonError(c, 'missing_identifier', 'Identifier is required.', 400);
      return c.json(await sdk.agents.createAgentVersion(payload));
    } catch (e: any) {
      return jsonError(c, 'create_agent_version_failed', e?.message || 'Unknown error', 500);
    }
  }

  // /agent/{identifier}/{statusAction}
  if (segments.length === 2) {
    const [identifier, statusAction] = segments;
    if (!['publish', 'unpublish', 'deprecate'].includes(statusAction))
      return jsonError(c, 'not_found', `Unknown agent action: ${statusAction}`, 404);
    if (c.req.method !== 'POST') return c.json({ error: 'method_not_allowed' }, 405);
    try {
      const fn =
        statusAction === 'publish'
          ? sdk.agents.publish
          : statusAction === 'unpublish'
            ? sdk.agents.unpublish
            : sdk.agents.deprecate;
      return c.json((await fn(identifier)) ?? { success: true });
    } catch (e: any) {
      return jsonError(c, `${statusAction}_agent_failed`, e?.message || 'Unknown error', 500);
    }
  }

  // GET /agent/{identifier}
  if (segments.length === 1 && c.req.method === 'GET') {
    try {
      return c.json(await sdk.agents.getAgentDetail(action));
    } catch (e: any) {
      return jsonError(c, 'get_agent_detail_failed', e?.message || 'Unknown error', 500);
    }
  }

  return jsonError(c, 'not_found', 'Requested agent endpoint is not available.', 404);
});

export default agent;
