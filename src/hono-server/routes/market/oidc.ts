import { Hono } from 'hono';

import { getTrustedClientTokenForSession } from '@/libs/trusted-client';
import { MarketService } from '@/server/services/market';

import { jsonError, MARKET_BASE_URL } from './helpers';

const ALLOWED_OIDC_ENDPOINTS = new Set(['handoff', 'token', 'userinfo']);

const oidc = new Hono();

oidc.all('/market/oidc/*', async (c) => {
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

export default oidc;
