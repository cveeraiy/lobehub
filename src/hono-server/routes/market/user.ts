import { Hono } from 'hono';

import { MarketService } from '@/server/services/market';

import { jsonError } from './helpers';

const user = new Hono();

user.put('/market/user/me', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;
  try {
    const payload = await c.req.json();
    if (typeof payload !== 'object' || payload === null)
      return jsonError(c, 'invalid_payload', 'Request body must be a JSON object', 400);

    const normalized = { ...payload, meta: payload.meta ?? {} };
    return c.json(await sdk.user.updateUserInfo(normalized));
  } catch (e: any) {
    const msg = e?.message || 'Unknown error';
    const isTaken = msg.toLowerCase().includes('already taken');
    return jsonError(
      c,
      isTaken ? 'username_taken' : 'update_user_profile_failed',
      msg,
      isTaken ? 409 : 500,
    );
  }
});

user.get('/market/user/:username', async (c) => {
  const username = decodeURIComponent(c.req.param('username'));
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;
  try {
    const response = await sdk.user.getUserInfo(username);
    if (!response?.user) return jsonError(c, 'user_not_found', `User not found: ${username}`, 404);
    const { user: u } = response;
    return c.json({
      avatarUrl: u.avatarUrl || null,
      bannerUrl: u.meta?.bannerUrl || null,
      createdAt: u.createdAt,
      description: u.meta?.description || null,
      displayName: u.displayName || null,
      id: u.id,
      namespace: u.namespace,
      socialLinks: u.meta?.socialLinks || null,
      type: u.type || null,
      userName: u.userName || null,
    });
  } catch (e: any) {
    return jsonError(c, 'get_user_profile_failed', e?.message || 'Unknown error', 500);
  }
});

export default user;
