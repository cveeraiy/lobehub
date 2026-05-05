import { type ChatCompletionErrorPayload } from '@lobechat/model-runtime';
import { AgentRuntimeError } from '@lobechat/model-runtime';
import { context as otContext } from '@lobechat/observability-otel/api';
import { type ClientSecretPayload } from '@lobechat/types';
import { ChatErrorType } from '@lobechat/types';
import { createMiddleware } from 'hono/factory';

import { auth } from '@/auth';
import { getServerDB } from '@/database/core/db-adaptor';
import { type LobeChatDatabase } from '@/database/type';
import { LOBE_CHAT_OIDC_AUTH_HEADER } from '@/envs/auth';
import { extractTraceContext, injectActiveTraceHeaders } from '@/libs/observability/traceparent';
import { validateOIDCJWT } from '@/libs/oidc-provider/jwt';
import { createErrorResponse } from '@/utils/errorResponse';

export interface AuthEnv {
  Variables: {
    jwtPayload: ClientSecretPayload;
    provider?: string;
    serverDB: LobeChatDatabase;
    userId: string;
  };
}

const isUnauthorizedAuthError = (error: unknown) => {
  return !!error && typeof error === 'object' && 'code' in error && error.code === 'UNAUTHORIZED';
};

/**
 * Hono middleware that authenticates the request via OIDC or better-auth session.
 * Sets `c.var.userId`, `c.var.serverDB`, and `c.var.jwtPayload` on success.
 */
export const authMiddleware = createMiddleware<AuthEnv>(async (c, next) => {
  const req = c.req.raw;
  const serverDB = await getServerDB();

  // Dev mock user
  const isDebugApi = req.headers.get('lobe-auth-dev-backend-api') === '1';
  const isMockUser = process.env.ENABLE_MOCK_DEV_USER === '1';
  if (process.env.NODE_ENV === 'development' && (isDebugApi || isMockUser)) {
    const mockUserId = process.env.MOCK_DEV_USER_ID || 'DEV_USER';
    c.set('userId', mockUserId);
    c.set('jwtPayload', { userId: mockUserId });
    c.set('serverDB', serverDB);
    return next();
  }

  let userId: string;
  const provider = c.req.param('provider');

  try {
    // OIDC authentication (CLI)
    const oidcAuthorization = req.headers.get(LOBE_CHAT_OIDC_AUTH_HEADER);
    if (oidcAuthorization) {
      const oidc = await validateOIDCJWT(oidcAuthorization);
      userId = oidc.userId;
    } else {
      // Better Auth session authentication (web)
      const session = await auth.api.getSession({
        headers: req.headers,
      });

      if (!session?.user?.id) {
        throw AgentRuntimeError.createError(ChatErrorType.Unauthorized);
      }

      userId = session.user.id;
    }
  } catch (e) {
    // if the error is not a ChatCompletionErrorPayload, it means the application error
    if (!(e as ChatCompletionErrorPayload).errorType) {
      if (isUnauthorizedAuthError(e)) {
        return createErrorResponse(ChatErrorType.Unauthorized, {
          error: e,
          provider,
        });
      }

      console.error(e);
      return createErrorResponse(ChatErrorType.InternalServerError, {
        error: e,
        provider,
      });
    }

    const {
      errorType = ChatErrorType.InternalServerError,
      error: errorContent,
      ...res
    } = e as ChatCompletionErrorPayload;

    const error = errorContent || e;
    return createErrorResponse(errorType, { error, ...res, provider });
  }

  c.set('userId', userId);
  c.set('jwtPayload', { userId });
  c.set('serverDB', serverDB);
  if (provider) c.set('provider', provider);

  // Execute handler within OpenTelemetry trace context
  const extractedContext = extractTraceContext(req.headers);

  const response = await otContext.with(extractedContext, () => next());

  // Inject trace headers into the response
  try {
    const headers = new Headers(c.res.headers);
    const traceparent = injectActiveTraceHeaders(headers);
    if (traceparent) {
      for (const [key, value] of headers) {
        c.res.headers.set(key, value);
      }
    }
  } catch (err) {
    console.error('Failed to inject trace headers:', err);
  }

  return response;
});
