// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  callPythonBackend,
  callPythonBackendStream,
  isPythonBackendEnabled,
  PythonBackendError,
} from './pythonBackend';

// Mock @/config/db — vi.hoisted ensures the object is available at mock-hoist time
const mockEnv = vi.hoisted(() => ({
  PYTHON_BACKEND_SERVICE_TOKEN: 'test-service-token',
  PYTHON_BACKEND_URL: 'http://localhost:8000',
}));

vi.mock('@/config/db', () => ({
  serverDBEnv: mockEnv,
}));

// Mock global fetch using vi.stubGlobal for reliable interception
const mockFetch = vi.fn<typeof fetch>();
vi.stubGlobal('fetch', mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
  mockEnv.PYTHON_BACKEND_URL = 'http://localhost:8000';
  mockEnv.PYTHON_BACKEND_SERVICE_TOKEN = 'test-service-token';
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── isPythonBackendEnabled ──────────────────────────────────────────

describe('isPythonBackendEnabled', () => {
  it('returns true when PYTHON_BACKEND_URL is set', () => {
    expect(isPythonBackendEnabled()).toBe(true);
  });

  it('returns false when PYTHON_BACKEND_URL is empty', () => {
    mockEnv.PYTHON_BACKEND_URL = '';
    expect(isPythonBackendEnabled()).toBe(false);
  });
});

// ── callPythonBackend ───────────────────────────────────────────────

describe('callPythonBackend', () => {
  it('throws when PYTHON_BACKEND_URL is not configured', async () => {
    mockEnv.PYTHON_BACKEND_URL = '';
    await expect(callPythonBackend('/api/test', 'user-1')).rejects.toThrow(
      'PYTHON_BACKEND_URL is not configured',
    );
  });

  it('makes a POST request by default with correct headers', async () => {
    const mockResponse = { operationId: 'op-123' };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }));

    const result = await callPythonBackend('/api/ai-agent/exec', 'user-42');

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/ai-agent/exec');
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({
      'Content-Type': 'application/json',
      'X-Internal-User-Id': 'user-42',
      'X-Service-Token': 'test-service-token',
    });
    expect(result).toEqual(mockResponse);
  });

  it('omits X-Service-Token when service token is not set', async () => {
    mockEnv.PYTHON_BACKEND_SERVICE_TOKEN = '';
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await callPythonBackend('/api/test', 'user-1');

    const headers = mockFetch.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers['X-Service-Token']).toBeUndefined();
    expect(headers['X-Internal-User-Id']).toBe('user-1');
  });

  it('uses the specified HTTP method', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await callPythonBackend('/api/test', 'user-1', { method: 'DELETE' });

    expect(mockFetch.mock.calls[0][1]?.method).toBe('DELETE');
  });

  it('serializes body as JSON', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    const body = { prompt: 'hello', agentId: 'agent-1' };
    await callPythonBackend('/api/ai-agent/exec', 'user-1', { body });

    expect(mockFetch.mock.calls[0][1]?.body).toBe(JSON.stringify(body));
  });

  it('does not include body when body is undefined', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await callPythonBackend('/api/test', 'user-1', { method: 'GET' });

    expect(mockFetch.mock.calls[0][1]?.body).toBeUndefined();
  });

  it('appends query parameters to URL', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await callPythonBackend('/api/test', 'user-1', {
      method: 'GET',
      query: { limit: 10, active: true, name: 'foo', skip: undefined },
    });

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('limit=10');
    expect(url).toContain('active=true');
    expect(url).toContain('name=foo');
    expect(url).not.toContain('skip');
  });

  // ── Error handling ──────────────────────────────────────────────

  it('throws PythonBackendError on non-OK JSON response', async () => {
    const errorBody = { detail: 'Agent not found' };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(errorBody), { status: 404 }));

    try {
      await callPythonBackend('/api/ai-agent/exec', 'user-1');
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PythonBackendError);
      const e = error as PythonBackendError;
      expect(e.status).toBe(404);
      expect(e.body).toEqual(errorBody);
    }
  });

  it('throws PythonBackendError with text body when JSON parse fails on error response', async () => {
    // Simulate a response where .json() throws but .text() succeeds
    const fakeResponse = {
      json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected token')),
      ok: false,
      status: 500,
      text: vi.fn().mockResolvedValue('Internal Server Error'),
    };
    mockFetch.mockResolvedValue(fakeResponse as any);

    try {
      await callPythonBackend('/api/test', 'user-1');
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PythonBackendError);
      const e = error as PythonBackendError;
      expect(e.status).toBe(500);
      expect(e.body).toBe('Internal Server Error');
    }
  });

  it('wraps network errors as PythonBackendError 502', async () => {
    mockFetch.mockRejectedValue(new TypeError('fetch failed'));

    try {
      await callPythonBackend('/api/test', 'user-1');
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PythonBackendError);
      const e = error as PythonBackendError;
      expect(e.status).toBe(502);
      expect(e.message).toContain('fetch failed');
    }
  });

  it('wraps timeout AbortError as PythonBackendError 504', async () => {
    mockFetch.mockRejectedValue(new DOMException('The operation was aborted', 'AbortError'));

    try {
      await callPythonBackend('/api/test', 'user-1', { timeout: 5000 });
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PythonBackendError);
      const e = error as PythonBackendError;
      expect(e.status).toBe(504);
      expect(e.message).toContain('timed out after 5000ms');
    }
  });
});

describe('callPythonBackendStream', () => {
  beforeEach(() => {
    mockEnv.PYTHON_BACKEND_URL = 'http://localhost:8000';
    mockEnv.PYTHON_BACKEND_SERVICE_TOKEN = 'test-service-token';
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('throws when PYTHON_BACKEND_URL is not configured', async () => {
    mockEnv.PYTHON_BACKEND_URL = '';

    await expect(callPythonBackendStream('/api/test', 'user-1')).rejects.toThrow(
      'PYTHON_BACKEND_URL is not configured',
    );
  });

  it('returns the raw Response on success', async () => {
    const fakeBody = new ReadableStream();
    mockFetch.mockResolvedValue({
      body: fakeBody,
      ok: true,
      status: 200,
    });

    const response = await callPythonBackendStream('/api/stream', 'user-1', {
      body: { prompt: 'hi' },
    });

    expect(response.ok).toBe(true);
    expect(response.body).toBe(fakeBody);

    // Verify the fetch was called with correct headers
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/stream',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Accept': 'text/event-stream',
          'Content-Type': 'application/json',
          'X-Internal-User-Id': 'user-1',
          'X-Service-Token': 'test-service-token',
        }),
        method: 'POST',
      }),
    );
  });

  it('does not set a timeout (SSE streams can run indefinitely)', async () => {
    mockFetch.mockResolvedValue({ body: new ReadableStream(), ok: true, status: 200 });

    await callPythonBackendStream('/api/stream', 'user-1');

    // Verify no AbortSignal timeout was passed (signal comes from caller or undefined)
    const callArgs = mockFetch.mock.calls[0][1];
    expect(callArgs.signal).toBeUndefined();
  });

  it('throws PythonBackendError on non-OK response', async () => {
    mockFetch.mockResolvedValue({
      json: vi.fn().mockResolvedValue({ detail: 'Bad request' }),
      ok: false,
      status: 400,
    });

    try {
      await callPythonBackendStream('/api/stream', 'user-1');
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PythonBackendError);
      const e = error as PythonBackendError;
      expect(e.status).toBe(400);
      expect(e.body).toEqual({ detail: 'Bad request' });
    }
  });

  it('passes signal through for client-side cancellation', async () => {
    const controller = new AbortController();
    mockFetch.mockResolvedValue({ body: new ReadableStream(), ok: true, status: 200 });

    await callPythonBackendStream('/api/stream', 'user-1', { signal: controller.signal });

    const callArgs = mockFetch.mock.calls[0][1];
    expect(callArgs.signal).toBe(controller.signal);
  });
});
