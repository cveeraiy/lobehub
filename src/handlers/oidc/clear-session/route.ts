import { serverDB } from '@lobechat/database';
import { oidcSessions } from '@lobechat/database/schemas';
import { getUserAuth } from '@lobechat/utils/server';
import debug from 'debug';
import { eq } from 'drizzle-orm';

const log = debug('lobe-oidc:clear-session');

function parseCookies(cookieHeader: string | null): Map<string, string> {
  const map = new Map<string, string>();
  if (!cookieHeader) return map;
  for (const pair of cookieHeader.split(';')) {
    const eqIdx = pair.indexOf('=');
    if (eqIdx === -1) continue;
    const key = pair.slice(0, eqIdx).trim();
    const value = pair.slice(eqIdx + 1).trim();
    map.set(key, value);
  }
  return map;
}

/**
 * POST /oidc/clear-session
 *
 * Clears the OIDC Provider session for the **current browser** only.
 *
 * Called by the frontend before `signOut()` so that when the user signs in
 * as a different account and an OIDC client later triggers `/authorize`,
 * the provider won't silently reuse the stale session that still points to
 * the old accountId.
 *
 * How it works:
 * 1. Read the `_session` cookie that `oidc-provider` sets in the browser.
 *    This cookie value is the primary key of the `oidc_sessions` table.
 * 2. Delete that single row from the database.
 * 3. Remove the `_session` and `_session.sig` cookies from the response so
 *    the browser no longer presents them.
 */
export async function POST(request?: Request) {
  try {
    // Ensure the caller is authenticated (still has a valid better-auth session)
    const { userId } = await getUserAuth(request);
    if (!userId) {
      return Response.json({ error: 'unauthorized' }, { status: 401 });
    }

    const cookieMap = parseCookies(request?.headers.get('cookie') ?? null);
    const sessionId = cookieMap.get('_session');

    if (!sessionId) {
      log('No _session cookie found, nothing to clear');
      return Response.json({ ok: true, cleared: false });
    }
    log('Clearing OIDC session %s for user %s', sessionId, userId);

    // Delete the OIDC session row from the database
    await serverDB.delete(oidcSessions).where(eq(oidcSessions.id, sessionId));

    // Build a response that also expires the browser cookies
    const cookieNames = ['_session', '_session.sig', '_session.legacy', '_session.legacy.sig'];
    const setCookieHeaders = cookieNames.map(
      (name) => `${name}=; Path=/; Expires=${new Date(0).toUTCString()}; HttpOnly`,
    );

    log('OIDC session cleared successfully');
    return new Response(JSON.stringify({ ok: true, cleared: true }), {
      headers: [
        ['Content-Type', 'application/json'],
        ...setCookieHeaders.map((v): [string, string] => ['Set-Cookie', v]),
      ],
      status: 200,
    });
  } catch (error) {
    log('Error clearing OIDC session: %O', error);
    // Non-fatal — don't block the sign-out flow
    return Response.json({ ok: true, cleared: false, error: 'internal' });
  }
}
