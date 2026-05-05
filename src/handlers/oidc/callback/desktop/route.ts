import debug from 'debug';
import { Response } from 'undici';

import { OAuthHandoffModel } from '@/database/models/oauthHandoff';
import { serverDB } from '@/database/server';
import { appEnv } from '@/envs/app';
import { afterResponse } from '@/server/utils/afterResponse';

const log = debug('lobe-oidc:callback:desktop');

const errorPathname = '/oauth/callback/error';

/**
 * Safely build redirect URL - directly use APP_URL as target
 */
const buildRedirectUrl = (req: Request, pathname: string): URL => {
  // Use unified environment variable management
  if (appEnv.APP_URL) {
    try {
      const baseUrl = new URL(appEnv.APP_URL);
      baseUrl.pathname = pathname;
      log('Using APP_URL for redirect: %s', baseUrl.toString());
      return baseUrl;
    } catch (error) {
      log('Error parsing APP_URL, using fallback: %O', error);
    }
  }

  // Fallback: use request URL as base
  log('Warning: APP_URL not configured, using request URL as fallback');
  const fallbackUrl = new URL(req.url);
  fallbackUrl.pathname = pathname;
  fallbackUrl.search = '';
  return fallbackUrl;
};

export const GET = async (req: Request) => {
  try {
    const searchParams = new URL(req.url).searchParams;
    const code = searchParams.get('code');
    const state = searchParams.get('state'); // This `state` is the handoff ID

    if (!code || !state || typeof code !== 'string' || typeof state !== 'string') {
      log('Missing code or state in form data');

      const errorUrl = buildRedirectUrl(req, errorPathname);
      errorUrl.searchParams.set('reason', 'invalid_request');

      log('Redirecting to error URL: %s', errorUrl.toString());
      return Response.redirect(errorUrl.toString());
    }

    log('Received OIDC callback. state(handoffId): %s', state);

    // The 'client' is 'desktop' because this redirect_uri is for the desktop client.
    const client = 'desktop';
    const payload = { code, state };
    const id = state;

    const authHandoffModel = new OAuthHandoffModel(serverDB);
    await authHandoffModel.create({ client, id, payload });
    log('Handoff record created successfully for id: %s', id);

    const successUrl = buildRedirectUrl(req, '/oauth/callback/success');

    // Add debug logging
    log('Request host header: %s', req.headers.get('host'));
    log('Request x-forwarded-host: %s', req.headers.get('x-forwarded-host'));
    log('Request x-forwarded-proto: %s', req.headers.get('x-forwarded-proto'));
    log('Constructed success URL: %s', successUrl.toString());

    // cleanup expired
    afterResponse(async () => {
      const cleanedCount = await authHandoffModel.cleanupExpired();

      log('Cleaned up %d expired handoff records', cleanedCount);
    });

    return Response.redirect(successUrl.toString());
  } catch (error) {
    log('Error in OIDC callback: %O', error);

    const errorUrl = buildRedirectUrl(req, errorPathname);
    errorUrl.searchParams.set('reason', 'internal_error');

    if (error instanceof Error) {
      errorUrl.searchParams.set('errorMessage', error.message);
    }

    log('Redirecting to error URL: %s', errorUrl.toString());
    return Response.redirect(errorUrl.toString());
  }
};
