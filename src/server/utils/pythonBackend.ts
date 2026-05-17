/**
 * Python Backend Proxy — typed fetch wrapper for calling the Python FastAPI backend.
 *
 * The TS backend acts as a reverse proxy: TRPC procedures call this helper
 * to delegate work to the Python backend while the frontend remains unchanged.
 *
 * Auth bridging: the TS backend forwards the authenticated userId via a trusted
 * `X-Internal-User-Id` header, protected by a shared service token.
 */

import debug from 'debug';

import { serverDBEnv } from '@/config/db';

const log = debug('lobe-server:python-backend');

export class PythonBackendError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message || `Python backend responded with ${status}`);
    this.name = 'PythonBackendError';
    this.status = status;
    this.body = body;
  }
}

interface CallOptions {
  body?: unknown;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** Query parameters appended to the URL */
  query?: Record<string, string | number | boolean | undefined>;
  /** Abort signal for request cancellation */
  signal?: AbortSignal;
  /** Request timeout in ms (default: 30 000) */
  timeout?: number;
}

/**
 * Call the Python backend.
 *
 * @param path   - URL path, e.g. `/api/ai-agent/exec`
 * @param userId - Authenticated user ID from the TRPC context
 * @param opts   - HTTP method, body, query params, etc.
 * @returns Parsed JSON response body
 */
export async function callPythonBackend<T = unknown>(
  path: string,
  userId: string,
  opts: CallOptions = {},
): Promise<T> {
  const baseUrl = serverDBEnv.PYTHON_BACKEND_URL;
  if (!baseUrl) {
    throw new Error(
      'PYTHON_BACKEND_URL is not configured. Set it in your .env to enable the Python backend proxy.',
    );
  }

  const { method = 'POST', body, query, signal, timeout = 30_000 } = opts;

  // Build URL with query params
  const url = new URL(path, baseUrl);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  // Headers: service token + userId forwarding
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Internal-User-Id': userId,
  };

  const serviceToken = serverDBEnv.PYTHON_BACKEND_SERVICE_TOKEN;
  if (serviceToken) {
    headers['X-Service-Token'] = serviceToken;
  }

  log('%s %s (user: %s)', method, url.pathname, userId);

  // Timeout via AbortController
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // Merge external signal
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const response = await fetch(url.toString(), {
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers,
      method,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }
      log('Error %d from %s: %O', response.status, url.pathname, errorBody);
      throw new PythonBackendError(response.status, errorBody);
    }

    const data = (await response.json()) as T;
    log('OK %s', url.pathname);
    return data;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof PythonBackendError) throw error;

    // Wrap network / timeout errors
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new PythonBackendError(
        504,
        null,
        `Python backend request timed out after ${timeout}ms`,
      );
    }

    log('Network error calling %s: %O', url.pathname, error);
    throw new PythonBackendError(
      502,
      null,
      `Failed to reach Python backend: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

/**
 * Call the Python backend and return the raw Response (for SSE streaming proxy).
 *
 * Unlike `callPythonBackend`, this does NOT parse the body — the caller is
 * responsible for piping `response.body` to the client.  The response is
 * validated for HTTP-level errors only.
 *
 * @param path   - URL path, e.g. `/api/ai-agent/exec/stream`
 * @param userId - Authenticated user ID
 * @param opts   - HTTP method, body, query params, etc.
 * @returns Raw `Response` with an SSE body stream
 */
export async function callPythonBackendStream(
  path: string,
  userId: string,
  opts: CallOptions = {},
): Promise<Response> {
  const baseUrl = serverDBEnv.PYTHON_BACKEND_URL;
  if (!baseUrl) {
    throw new Error(
      'PYTHON_BACKEND_URL is not configured. Set it in your .env to enable the Python backend proxy.',
    );
  }

  const { method = 'POST', body, query, signal } = opts;

  const url = new URL(path, baseUrl);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers: Record<string, string> = {
    'Accept': 'text/event-stream',
    'Content-Type': 'application/json',
    'X-Internal-User-Id': userId,
  };

  const serviceToken = serverDBEnv.PYTHON_BACKEND_SERVICE_TOKEN;
  if (serviceToken) {
    headers['X-Service-Token'] = serviceToken;
  }

  log('STREAM %s %s (user: %s)', method, url.pathname, userId);

  // No timeout for SSE — the stream can run for minutes.
  // Client disconnect (signal abort) terminates the upstream fetch.
  const response = await fetch(url.toString(), {
    body: body !== undefined ? JSON.stringify(body) : undefined,
    headers,
    method,
    signal,
  });

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = await response.text();
    }
    log('Stream error %d from %s: %O', response.status, url.pathname, errorBody);
    throw new PythonBackendError(response.status, errorBody);
  }

  log('Stream connected %s', url.pathname);
  return response;
}

/**
 * Check if the Python backend proxy is enabled.
 */
export function isPythonBackendEnabled(): boolean {
  return !!serverDBEnv.PYTHON_BACKEND_URL;
}
