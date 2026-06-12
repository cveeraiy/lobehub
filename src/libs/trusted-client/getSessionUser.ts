import { type TrustedClientUserInfo } from './index';

/**
 * Get user info from the current session for trusted client authentication
 *
 * @param request - The incoming HTTP request (used to read session headers)
 * @returns User info or undefined if not authenticated
 */
export const getSessionUser = async (
  request: Request,
): Promise<TrustedClientUserInfo | undefined> => {
  try {
    // Dynamic import to avoid validator ESM/CJS issue during sitemap generation
    const { auth } = await import('@/auth');
    const session = await auth.api.getSession({
      headers: request.headers,
    });

    if (!session?.user?.id || !session?.user?.email) {
      return undefined;
    }

    return {
      email: session.user.email,
      name: session.user.name || undefined,
      userId: session.user.id,
    };
  } catch {
    return undefined;
  }
};
