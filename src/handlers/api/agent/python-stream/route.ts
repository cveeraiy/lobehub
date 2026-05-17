/**
 * SSE proxy handler for the Python backend's agent stream.
 *
 * Registered at `POST /api/agent/python-stream` behind `authMiddleware`.
 * The Hono route passes the authenticated `userId` from `c.get('userId')`.
 */

import debug from 'debug';

import { callPythonBackendStream, PythonBackendError } from '@/server/utils/pythonBackend';

const log = debug('api-route:agent:python-stream');

export async function POST(request: Request, userId: string): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  log('Python stream proxy for user %s', userId);

  try {
    const upstreamResponse = await callPythonBackendStream('/api/ai-agent/exec/stream', userId, {
      body,
      method: 'POST',
      signal: request.signal,
    });

    // Pipe the SSE stream straight through to the client.
    const headers = new Headers();
    headers.set('Content-Type', 'text/event-stream');
    headers.set('Cache-Control', 'no-cache');
    headers.set('Connection', 'keep-alive');
    headers.set('X-Accel-Buffering', 'no'); // Disable nginx buffering

    return new Response(upstreamResponse.body, {
      headers,
      status: 200,
    });
  } catch (error) {
    if (error instanceof PythonBackendError) {
      log('Python stream error %d: %O', error.status, error.body);
      return Response.json({ detail: error.body || error.message }, { status: error.status });
    }

    log('Python stream unexpected error: %O', error);
    return Response.json({ error: 'Failed to connect to Python backend stream' }, { status: 502 });
  }
}
