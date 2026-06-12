import debug from 'debug';
import Redis from 'ioredis';

import { redisEnv } from '@/envs/redis';
import { isRedisDisabledByEnv } from '@/libs/redis';

const log = debug('ethos-server:runtime-redis');
const timing = debug('ethos-server:runtime-redis:timing');

const getRedisConnectionDescription = (url: string): string => {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return 'redis://***';
  }
};

export const createRuntimeRedisClient = (url?: string): Redis | null => {
  if (isRedisDisabledByEnv()) return null;

  const redisUrl = url || redisEnv.REDIS_URL;

  if (!redisUrl) {
    console.warn('[Runtime Redis] No Redis URL available. Runtime Redis features are disabled.');
    return null;
  }

  const createStart = Date.now();
  timing('Redis client creating at %d', createStart);

  const client = new Redis(redisUrl, {
    maxRetriesPerRequest: 3,
  });

  client.on('connect', () => {
    const connectTime = Date.now();
    log('Connected to Redis: %s', getRedisConnectionDescription(redisUrl));
    timing(
      'Redis connected at %d, took %dms from creation',
      connectTime,
      connectTime - createStart,
    );
  });

  client.on('ready', () => {
    const readyTime = Date.now();
    timing('Redis ready at %d, took %dms from creation', readyTime, readyTime - createStart);
  });

  client.on('error', (error) => {
    console.error('[Runtime Redis] Redis connection error:', error);
  });

  client.on('close', () => {
    log('Redis connection closed');
  });

  return client;
};

let globalRuntimeRedisClient: Redis | null = null;
let redisInitialized = false;

export function getRuntimeRedisClient(): Redis | null {
  if (!redisInitialized) {
    timing('Redis client not initialized, creating new instance at %d', Date.now());
    globalRuntimeRedisClient = createRuntimeRedisClient();
    redisInitialized = true;
  } else {
    timing('Redis client already initialized, reusing at %d', Date.now());
  }

  return globalRuntimeRedisClient;
}

export async function closeRuntimeRedisClient(): Promise<void> {
  if (globalRuntimeRedisClient) {
    await globalRuntimeRedisClient.quit();
    globalRuntimeRedisClient = null;
    redisInitialized = false;
  }
}

export const createAgentRuntimeRedisClient = createRuntimeRedisClient;
export const getAgentRuntimeRedisClient = getRuntimeRedisClient;
export const closeAgentRuntimeRedisClient = closeRuntimeRedisClient;
