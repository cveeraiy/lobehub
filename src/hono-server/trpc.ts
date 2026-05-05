import { fetchRequestHandler } from '@trpc/server/adapters/fetch';
import { Hono } from 'hono';

import { createAsyncRouteContext } from '@/libs/trpc/async/context';
import { createLambdaContext } from '@/libs/trpc/lambda/context';
import { createResponseMeta } from '@/libs/trpc/utils/responseMeta';
import { asyncRouter } from '@/server/routers/async';
import { lambdaRouter } from '@/server/routers/lambda';
import { mobileRouter } from '@/server/routers/mobile';
import { toolsRouter } from '@/server/routers/tools';

const trpcApp = new Hono();

// ============ Lambda Router ============ //
trpcApp.all('/trpc/lambda/*', async (c) => {
  return fetchRequestHandler({
    createContext: () => createLambdaContext(c.req.raw),
    endpoint: '/trpc/lambda',
    onError: ({ error, path, type }) => {
      if (error.code === 'UNAUTHORIZED') return;
      console.info(`Error in tRPC handler (lambda) on path: ${path}, type: ${type}`);
      console.error(error);
    },
    req: c.req.raw,
    responseMeta: createResponseMeta,
    router: lambdaRouter,
  });
});

// ============ Async Router ============ //
trpcApp.all('/trpc/async/*', async (c) => {
  return fetchRequestHandler({
    allowBatching: false,
    createContext: () => createAsyncRouteContext(c.req.raw),
    endpoint: '/trpc/async',
    onError: ({ error, path, type }) => {
      console.info(`Error in tRPC handler (async) on path: ${path}, type: ${type}`);
      console.error(error);
    },
    req: c.req.raw,
    responseMeta: createResponseMeta,
    router: asyncRouter,
  });
});

// ============ Mobile Router ============ //
trpcApp.all('/trpc/mobile/*', async (c) => {
  return fetchRequestHandler({
    createContext: () => createLambdaContext(c.req.raw),
    endpoint: '/trpc/mobile',
    onError: ({ error, path, type }) => {
      console.info(`Error in tRPC handler (mobile) on path: ${path}, type: ${type}`);
      console.error(error);
    },
    req: c.req.raw,
    responseMeta: createResponseMeta,
    router: mobileRouter,
  });
});

// ============ Tools Router ============ //
trpcApp.all('/trpc/tools/*', async (c) => {
  return fetchRequestHandler({
    createContext: () => createLambdaContext(c.req.raw),
    endpoint: '/trpc/tools',
    onError: ({ error, path, type }) => {
      console.error(`Error in tRPC handler (tools) on path: ${path}, type: ${type}`);
      console.error(error);
    },
    req: c.req.raw,
    responseMeta: createResponseMeta,
    router: toolsRouter,
  });
});

export default trpcApp;
