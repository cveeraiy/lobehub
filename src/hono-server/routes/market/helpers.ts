import type { Context } from 'hono';

export const jsonError = (c: Context, error: string, message: string, status: number) =>
  c.json({ error, message, status: 'error' }, status as any);

export const MARKET_BASE_URL = process.env.MARKET_BASE_URL || 'https://market.lobehub.com';
