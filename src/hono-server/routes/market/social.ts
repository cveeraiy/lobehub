import { Hono } from 'hono';

import { MarketService } from '@/server/services/market';

import { jsonError, MARKET_BASE_URL } from './helpers';

const social = new Hono();

social.get('/market/social-profile/claimable-resources', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);

  try {
    const headers = (marketService.market as any).headers as Record<string, string>;
    const response = await fetch(`${MARKET_BASE_URL}/api/v1/user/claims/scan`, {
      headers,
      method: 'GET',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return jsonError(
        c,
        'scan_claimable_resources_failed',
        errorData.error || `Failed to scan claimable resources: ${response.status}`,
        response.status,
      );
    }

    const responseData = await response.json();
    const data = responseData.data || responseData;

    return c.json({
      plugins: data.plugins || [],
      skills: data.skills || [],
    });
  } catch (e: any) {
    console.error('[Market SocialProfile] Scan claimable resources failed:', e);
    return jsonError(c, 'scan_claimable_resources_failed', e?.message || 'Unknown error', 500);
  }
});

social.post('/market/social-profile/claim-resources', async (c) => {
  const marketService = await MarketService.createFromRequest(c.req.raw);

  try {
    const body = (await c.req.json()) as {
      pluginIds?: string[];
      skillIds?: string[];
    };
    const headers = (marketService.market as any).headers as Record<string, string>;

    const claimed: Array<{ assetId: number; assetType: 'plugin' | 'skill' }> = [];
    const errors: string[] = [];

    for (const skillId of body.skillIds || []) {
      try {
        const response = await fetch(`${MARKET_BASE_URL}/api/v1/user/claims`, {
          body: JSON.stringify({ assetId: Number(skillId), assetType: 'skill' }),
          headers: {
            ...headers,
            'Content-Type': 'application/json',
          },
          method: 'POST',
        });

        if (response.ok) {
          claimed.push({ assetId: Number(skillId), assetType: 'skill' });
        } else {
          const error = await response.json().catch(() => ({}));
          errors.push(error.error || `Failed to claim skill ${skillId}`);
        }
      } catch {
        errors.push(`Failed to claim skill ${skillId}`);
      }
    }

    for (const pluginId of body.pluginIds || []) {
      try {
        const response = await fetch(`${MARKET_BASE_URL}/api/v1/user/claims`, {
          body: JSON.stringify({ assetId: Number(pluginId), assetType: 'plugin' }),
          headers: {
            ...headers,
            'Content-Type': 'application/json',
          },
          method: 'POST',
        });

        if (response.ok) {
          claimed.push({ assetId: Number(pluginId), assetType: 'plugin' });
        } else {
          const error = await response.json().catch(() => ({}));
          errors.push(error.error || `Failed to claim plugin ${pluginId}`);
        }
      } catch {
        errors.push(`Failed to claim plugin ${pluginId}`);
      }
    }

    if (claimed.length === 0 && errors.length > 0) {
      return jsonError(c, 'claim_resources_failed', errors[0], 500);
    }

    return c.json({
      claimed,
      errors: errors.length > 0 ? errors : undefined,
      success: claimed.length > 0,
    });
  } catch (e: any) {
    console.error('[Market SocialProfile] Claim resources failed:', e);
    return jsonError(c, 'claim_resources_failed', e?.message || 'Unknown error', 500);
  }
});

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
