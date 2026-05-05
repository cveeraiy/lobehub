import { Hono } from 'hono';

import { MarketService } from '@/server/services/market';

import { jsonError } from './helpers';

const social = new Hono();

social.post('/market/social/*', async (c) => {
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

social.get('/market/social/*', async (c) => {
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

export default social;
