import { Hono } from 'hono';

import { auth } from '@/auth';

const authApp = new Hono();

// better-auth exposes a standard fetch-compatible handler via auth.handler
// Mount it on /api/auth/* to match the existing Next.js route
authApp.all('/api/auth/*', async (c) => {
  return auth.handler(c.req.raw);
});

export default authApp;
