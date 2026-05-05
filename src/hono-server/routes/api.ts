import lobeOpenApi from '@lobechat/openapi';
import debug from 'debug';
import { and, eq } from 'drizzle-orm';
import { Hono } from 'hono';

import { FileModel } from '@/database/models/file';
import { account } from '@/database/schemas/betterAuth';
import { users } from '@/database/schemas/user';
import { getServerDB } from '@/database/server';
import { getRedisConfig } from '@/envs/redis';
import { POST as benchmarkLocomo } from '@/handlers/api/dev/memory-user-memory/benchmark-locomo/route';
import { initializeRedis, isRedisEnabled } from '@/libs/redis';
import { FileService } from '@/server/services/file';
import { UserService } from '@/server/services/user';

import pkg from '../../../package.json';

const log = debug('lobe-file:proxy');
const api = new Hono();

// ============ Version ============ //
api.get('/api/version', (c) => {
  return c.json({ version: pkg.version });
});

// ============ Auth: Check User ============ //
api.post('/api/auth/check-user', async (c) => {
  try {
    const body = await c.req.json();
    const { email } = body;

    if (!email || typeof email !== 'string') {
      return c.json({ error: 'Email is required', exists: false }, 400);
    }

    const db = await getServerDB();

    const [user] = await db
      .select({ emailVerified: users.emailVerified, id: users.id })
      .from(users)
      .where(eq(users.email, email.toLowerCase().trim()))
      .limit(1);

    if (!user) {
      return c.json({ exists: false });
    }

    const accounts = await db
      .select({ password: account.password, providerId: account.providerId })
      .from(account)
      .where(and(eq(account.userId, user.id)));

    const hasPassword = accounts.some(
      (a) =>
        a.providerId === 'credential' && typeof a.password === 'string' && a.password.length > 0,
    );

    return c.json({ exists: true, hasPassword });
  } catch (error) {
    console.error('Error checking user existence:', error);
    return c.json({ error: 'Internal server error', exists: false }, 500);
  }
});

// ============ Auth: Resolve Username ============ //
api.post('/api/auth/resolve-username', async (c) => {
  try {
    const body = await c.req.json();
    const { username } = body;

    if (!username || typeof username !== 'string') {
      return c.json({ error: 'Username is required', exists: false }, 400);
    }

    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      return c.json({ error: 'Username is required', exists: false }, 400);
    }

    const db = await getServerDB();

    const [user] = await db
      .select({ email: users.email })
      .from(users)
      .where(eq(users.username, normalizedUsername))
      .limit(1);

    if (!user || !user.email) {
      return c.json({ exists: false });
    }

    return c.json({ email: user.email, exists: true });
  } catch (error) {
    console.error('Error resolving username to email:', error);
    return c.json({ error: 'Internal server error', exists: false }, 500);
  }
});

// ============ OpenAI-compatible v1 API ============ //
api.all('/api/v1/*', (c) => lobeOpenApi.fetch(c.req.raw));

// ============ File Proxy ============ //
const FILE_PROXY_KEY_PREFIX = 'file-proxy:';
const PRESIGNED_URL_CACHE_TTL = 240;

api.get('/f/:id', async (c) => {
  try {
    const id = c.req.param('id');
    log('File proxy request: %s', id);

    const redisConfig = getRedisConfig();
    const redisClient = isRedisEnabled(redisConfig) ? await initializeRedis(redisConfig) : null;

    const cacheKey = `${FILE_PROXY_KEY_PREFIX}${id}`;
    if (redisClient) {
      const cachedStr = await redisClient.get(cacheKey);
      const cached = cachedStr ? (JSON.parse(cachedStr) as { redirectUrl: string }) : null;
      if (cached?.redirectUrl) {
        log('Cache hit for file: %s', id);
        return c.redirect(cached.redirectUrl, 302);
      }
      log('Cache miss for file: %s', id);
    }

    const db = await getServerDB();
    const file = await FileModel.getFileById(db, id);

    if (!file) {
      log('File not found: %s', id);
      return c.text('File not found', 404);
    }

    const fileService = new FileService(db, file.userId);
    const redirectUrl = await fileService.createPreSignedUrlForPreview(file.url, 300);
    log('Web S3 presigned URL generated (expires in 5 min)');

    if (redisClient) {
      await redisClient.set(cacheKey, JSON.stringify({ redirectUrl }), {
        ex: PRESIGNED_URL_CACHE_TTL,
      });
      log('Cached presigned URL for file: %s (TTL: %ds)', id, PRESIGNED_URL_CACHE_TTL);
    }

    return c.redirect(redirectUrl, 302);
  } catch (error) {
    console.error('File proxy error:', error);
    return c.text('Internal server error', 500);
  }
});

// ============ User Avatar ============ //
const CONTENT_TYPE_MAP: Record<string, string> = {
  avif: 'image/avif',
  bmp: 'image/bmp',
  gif: 'image/gif',
  heic: 'image/heic',
  heif: 'image/heif',
  ico: 'image/x-icon',
  jpeg: 'image/jpeg',
  jpg: 'image/jpg',
  png: 'image/png',
  svg: 'image/svg+xml',
  tif: 'image/tiff',
  tiff: 'image/tiff',
  webp: 'image/webp',
};

api.get('/webapi/user/avatar/:id/:image', async (c) => {
  try {
    const id = c.req.param('id');
    const image = c.req.param('image');
    const extension = image.split('.').pop()?.toLowerCase() || '';
    const contentType = CONTENT_TYPE_MAP[extension] || 'application/octet-stream';

    const db = await getServerDB();
    const userService = new UserService(db);
    const userAvatar = await userService.getUserAvatar(id, image);

    if (!userAvatar) {
      return c.text('Avatar not found', 404);
    }

    return new Response(userAvatar, {
      headers: {
        'Cache-Control': 'public, max-age=31536000, immutable',
        'Content-Type': contentType,
      },
      status: 200,
    });
  } catch (error) {
    console.error('Error fetching user avatar:', error);
    return c.text('Internal server error', 500);
  }
});

// ============ Dev: Benchmark LoCoMo ============ //
api.post('/api/dev/memory-user-memory/benchmark-locomo', (c) => benchmarkLocomo(c.req.raw));

export default api;
