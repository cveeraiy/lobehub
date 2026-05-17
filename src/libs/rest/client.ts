import debug from 'debug';

import { withElectronProtocolIfElectron } from '@/const/protocol';

import type { RestApiError } from './types';

const log = debug('lobe-rest:client');

// ---------------------------------------------------------------------------
// 401 debouncing — mirrors the TRPC lambda client behaviour
// ---------------------------------------------------------------------------
let last401Time = 0;
let lastMarket401Time = 0;
const MIN_401_INTERVAL = 5000;

// ---------------------------------------------------------------------------
// Base URL — relative path so it goes through the same origin / dev proxy.
// The Python backend is mounted behind the same host (via Vite proxy or
// reverse-proxy in production).
// ---------------------------------------------------------------------------
const REST_BASE = withElectronProtocolIfElectron('/api');

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

export class RestClientError extends Error {
  status: number;
  code?: string;
  meta?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'RestClientError';
    this.status = status;
    this.code = code;
  }
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

interface RequestOptions extends Omit<RequestInit, 'method' | 'body'> {
  /** Override base path (default: `/api`) */
  basePath?: string;
  /** JSON body — will be serialised automatically */
  body?: unknown;
  /** Query params appended to the URL */
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { basePath = REST_BASE, body, params, headers: extraHeaders, ...fetchOpts } = options;

  // Build URL with query params
  let url = `${basePath}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const qsStr = qs.toString();
    if (qsStr) url += `?${qsStr}`;
  }

  // Auth headers — dynamic import to avoid circular dependency
  const { createHeaderWithAuth } = await import('@/services/_auth');
  const authHeaders = await createHeaderWithAuth();

  const init: RequestInit = {
    ...fetchOpts,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...extraHeaders,
    },
    method,
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  log('%s %s', method, url);

  const res = await fetch(url, init);

  // Handle 401 — mirrors TRPC lambda client logic
  if (res.status === 401) {
    await handle401(path);
  }

  // Non-2xx → throw typed error
  if (!res.ok) {
    let detail: string | undefined;
    let code: string | undefined;
    try {
      const errJson = (await res.json()) as RestApiError;
      detail = errJson.detail || errJson.message;
      code = errJson.code;
    } catch {
      detail = res.statusText;
    }
    throw new RestClientError(detail || `HTTP ${res.status}`, res.status, code);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// 401 handler (matches TRPC lambda client)
// ---------------------------------------------------------------------------

async function handle401(path: string) {
  const isMarketApi = path.startsWith('/market');
  const now = Date.now();

  if (isMarketApi) {
    if (now - lastMarket401Time > MIN_401_INTERVAL) {
      lastMarket401Time = now;
      const { marketAuthEvents } = await import('@/layout/AuthProvider/MarketAuth/events');
      marketAuthEvents.emit('market-unauthorized', { path, timestamp: now });
    }
  } else {
    if (now - last401Time > MIN_401_INTERVAL) {
      last401Time = now;
      const { getUserStoreState } = await import('@/store/user/store');
      const { isSignedIn, logout } = getUserStoreState();
      if (isSignedIn) {
        await logout();
      }
      const { loginRequired } = await import('@/components/Error/loginRequiredNotification');
      loginRequired.redirect();
    }
  }
}

// ---------------------------------------------------------------------------
// Convenience methods
// ---------------------------------------------------------------------------

export const restClient = {
  delete: <T = void>(path: string, opts?: RequestOptions) => request<T>('DELETE', path, opts),

  get: <T>(path: string, opts?: RequestOptions) => request<T>('GET', path, opts),

  patch: <T>(path: string, opts?: RequestOptions) => request<T>('PATCH', path, opts),

  post: <T>(path: string, opts?: RequestOptions) => request<T>('POST', path, opts),

  put: <T>(path: string, opts?: RequestOptions) => request<T>('PUT', path, opts),
};
