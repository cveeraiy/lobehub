import { Hono } from 'hono';

import { getTrustedClientTokenForSession } from '@/libs/trusted-client';
import { MarketService } from '@/server/services/market';

const MARKET_BASE_URL = process.env.MARKET_BASE_URL || 'https://market.lobehub.com';

const market = new Hono();

// ──────────── helpers ──────────── //

const jsonError = (c: any, error: string, message: string, status: number) =>
  c.json({ error, message, status: 'error' }, status);

// ──────────── /market/agent/* ──────────── //

market.all('/market/agent/*', async (c) => {
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

// ──────────── /market/social/* ──────────── //

market.post('/market/social/*', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;
  const action = c.req.path.replace('/market/social/', '').split('/')[0];

  try {
    const body = await c.req.json();
    switch (action) {
      case 'follow': {
        await sdk.follows.follow(body.followingId);
        return c.json({ success: true });
      }
      case 'unfollow': {
        await sdk.follows.unfollow(body.followingId);
        return c.json({ success: true });
      }
      case 'favorite': {
        await sdk.favorites.addFavorite(body.targetType, body.identifier ?? body.targetId);
        return c.json({ success: true });
      }
      case 'unfavorite': {
        await sdk.favorites.removeFavorite(body.targetType, body.identifier ?? body.targetId);
        return c.json({ success: true });
      }
      case 'like': {
        await sdk.likes.like(body.targetType, body.identifier ?? body.targetId);
        return c.json({ success: true });
      }
      case 'unlike': {
        await sdk.likes.unlike(body.targetType, body.identifier ?? body.targetId);
        return c.json({ success: true });
      }
      case 'toggle-like': {
        return c.json(
          await sdk.likes.toggleLike(body.targetType, body.identifier ?? body.targetId),
        );
      }
      default: {
        return jsonError(c, 'not_found', `Unknown action: ${action}`, 404);
      }
    }
  } catch (e: any) {
    console.error('[Market Social] Action failed:', e);
    return jsonError(c, 'action_failed', e?.message || 'Unknown error', 500);
  }
});

market.get('/market/social/*', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;
  const fullPath = c.req.path.replace('/market/social/', '');
  const segments = fullPath.split('/');
  const action = segments[0];

  const url = new URL(c.req.url);
  const limit = url.searchParams.get('pageSize') || url.searchParams.get('limit');
  const offset = url.searchParams.get('offset');
  const paginationParams: { limit?: number; offset?: number } = {};
  if (limit) paginationParams.limit = Number(limit);
  if (offset) paginationParams.offset = Number(offset);

  try {
    switch (action) {
      case 'follow-status': {
        return c.json(await sdk.follows.checkFollowStatus(Number(segments[1])));
      }
      case 'following': {
        return c.json(await sdk.follows.getFollowing(Number(segments[1]), paginationParams));
      }
      case 'followers': {
        return c.json(await sdk.follows.getFollowers(Number(segments[1]), paginationParams));
      }
      case 'follow-counts': {
        const userId = Number(segments[1]);
        const [following, followers] = await Promise.all([
          sdk.follows.getFollowing(userId, { limit: 1 }),
          sdk.follows.getFollowers(userId, { limit: 1 }),
        ]);
        return c.json({
          followersCount: (followers as any).totalCount || (followers as any).total || 0,
          followingCount: (following as any).totalCount || (following as any).total || 0,
        });
      }
      case 'favorite-status': {
        const targetType = segments[1] as 'agent' | 'plugin';
        const val = /^\d+$/.test(segments[2]) ? Number(segments[2]) : segments[2];
        return c.json(await sdk.favorites.checkFavorite(targetType, val as number));
      }
      case 'favorites': {
        return c.json(await sdk.favorites.getMyFavorites(paginationParams));
      }
      case 'user-favorites': {
        return c.json(await sdk.favorites.getUserFavorites(Number(segments[1]), paginationParams));
      }
      case 'favorite-agents': {
        return c.json(
          await sdk.favorites.getUserFavoriteAgents(Number(segments[1]), paginationParams),
        );
      }
      case 'favorite-plugins': {
        return c.json(
          await sdk.favorites.getUserFavoritePlugins(Number(segments[1]), paginationParams),
        );
      }
      case 'like-status': {
        const targetType = segments[1] as 'agent' | 'plugin';
        const val = /^\d+$/.test(segments[2]) ? Number(segments[2]) : segments[2];
        return c.json(await sdk.likes.checkLike(targetType, val as number));
      }
      case 'liked-agents': {
        return c.json(await sdk.likes.getUserLikedAgents(Number(segments[1]), paginationParams));
      }
      case 'liked-plugins': {
        return c.json(await sdk.likes.getUserLikedPlugins(Number(segments[1]), paginationParams));
      }
      default: {
        return jsonError(c, 'not_found', `Unknown action: ${action}`, 404);
      }
    }
  } catch (e: any) {
    console.error('[Market Social] Query failed:', e);
    return jsonError(c, 'query_failed', e?.message || 'Unknown error', 500);
  }
});

// ──────────── /market/user/* ──────────── //

market.put('/market/user/me', async (c) => {
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

market.get('/market/user/:username', async (c) => {
  const username = decodeURIComponent(c.req.param('username'));
  const marketService = await MarketService.createFromRequest(c.req.raw);
  const sdk = marketService.market;
  try {
    const response = await sdk.user.getUserInfo(username);
    if (!response?.user) return jsonError(c, 'user_not_found', `User not found: ${username}`, 404);
    const { user } = response;
    return c.json({
      avatarUrl: user.avatarUrl || null,
      bannerUrl: user.meta?.bannerUrl || null,
      createdAt: user.createdAt,
      description: user.meta?.description || null,
      displayName: user.displayName || null,
      id: user.id,
      namespace: user.namespace,
      socialLinks: user.meta?.socialLinks || null,
      type: user.type || null,
      userName: user.userName || null,
    });
  } catch (e: any) {
    return jsonError(c, 'get_user_profile_failed', e?.message || 'Unknown error', 500);
  }
});

// ──────────── /market/oidc/* ──────────── //

const ALLOWED_OIDC_ENDPOINTS = new Set(['handoff', 'token', 'userinfo']);

market.all('/market/oidc/*', async (c) => {
  const sdk = new MarketService().market;
  const fullPath = c.req.path.replace('/market/oidc/', '').replace('/market/oidc', '');
  const segments = fullPath ? fullPath.split('/') : [];

  if (segments.length !== 1 || !ALLOWED_OIDC_ENDPOINTS.has(segments[0]))
    return jsonError(c, 'not_found', 'Requested endpoint is not available.', 404);

  const endpoint = segments[0];

  switch (endpoint) {
    case 'handoff': {
      try {
        const id = new URL(c.req.url).searchParams.get('id');
        if (!id) return jsonError(c, 'missing_id', 'ID is required for handoff proxy.', 400);
        return c.json(await sdk.auth.getOAuthHandoff(id));
      } catch (e: any) {
        return jsonError(c, 'handoff_proxy_failed', e?.message || 'Unknown error', 500);
      }
    }

    case 'token': {
      if (c.req.method !== 'POST') return c.json({ error: 'method_not_allowed' }, 405);
      try {
        const body = await c.req.text();
        const form = new URLSearchParams(body);
        const grantType = (form.get('grant_type') || 'authorization_code') as
          | 'authorization_code'
          | 'refresh_token';

        if (grantType === 'authorization_code') {
          return c.json(
            await sdk.auth.exchangeOAuthToken({
              clientId: form.get('client_id') as string,
              code: form.get('code') as string,
              codeVerifier: form.get('code_verifier') as string,
              grantType: 'authorization_code',
              redirectUri: form.get('redirect_uri') as string,
            }),
          );
        }
        if (grantType === 'refresh_token') {
          return c.json(
            await sdk.auth.exchangeOAuthToken({
              clientId: form.get('client_id') ?? undefined,
              grantType: 'refresh_token',
              refreshToken: form.get('refresh_token') as string,
            }),
          );
        }
        return jsonError(c, 'unsupported_grant_type', `Unsupported grant_type: ${grantType}`, 400);
      } catch (e: any) {
        console.error('[MarketOIDC] token proxy failed:', e);
        return jsonError(c, 'token_proxy_failed', e?.message || 'Unknown error', 500);
      }
    }

    case 'userinfo': {
      if (c.req.method !== 'POST') return c.json({ error: 'method_not_allowed' }, 405);
      try {
        const { token } = (await c.req.json()) as { token?: string };
        if (!token) {
          const trustedClientToken = await getTrustedClientTokenForSession();
          if (!trustedClientToken)
            return jsonError(c, 'missing_token', 'Token is required for userinfo proxy.', 400);
          const res = await fetch(`${MARKET_BASE_URL}/lobehub-oidc/userinfo`, {
            headers: {
              'Content-Type': 'application/json',
              'x-lobe-trust-token': trustedClientToken,
            },
            method: 'GET',
          });
          if (!res.ok)
            throw new Error(`Failed to fetch user info: ${res.status} ${res.statusText}`);
          return c.json(await res.json());
        }
        return c.json(await sdk.auth.getUserInfo(token));
      } catch (e: any) {
        console.error('[MarketOIDC] userinfo proxy failed:', e);
        return jsonError(c, 'userinfo_proxy_failed', e?.message || 'Unknown error', 500);
      }
    }

    default: {
      return jsonError(c, 'unsupported_endpoint', 'Requested endpoint is not supported.', 404);
    }
  }
});

export default market;
