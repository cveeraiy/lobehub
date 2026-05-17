/**
 * Python Stream Bridge
 *
 * Consumes the Python backend's SSE stream and republishes events to the
 * TS StreamEventManager (Redis/InMemory).  This lets the existing frontend
 * SSE endpoint (`GET /api/agent/stream`) work without any changes — the
 * events look as if they were emitted by the TS agent runtime.
 *
 * Usage (fire-and-forget after execAgent proxy returns):
 *
 *   bridgePythonStream(operationId, userId, execInput);
 */

import debug from 'debug';

import { createStreamEventManager } from '@/server/modules/AgentRuntime';
import { type IStreamEventManager } from '@/server/modules/AgentRuntime';
import { callPythonBackendStream } from '@/server/utils/pythonBackend';

const log = debug('lobe-server:python-stream-bridge');

/**
 * Parse a raw SSE text frame into { event, data }.
 *
 * Standard SSE format:
 *   event: <type>\n
 *   data: <json>\n
 *   \n
 */
function parseSSEFrame(raw: string): { data: string; event: string } | null {
  let event = 'message';
  let data = '';

  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data += line.slice(5).trim();
    }
  }

  if (!data) return null;
  return { data, event };
}

/**
 * Map a Python SSE event type to a TS StreamEvent type.
 */
function mapEventType(
  pythonType: string,
):
  | 'agent_runtime_init'
  | 'agent_runtime_end'
  | 'stream_chunk'
  | 'stream_start'
  | 'stream_end'
  | 'tool_start'
  | 'tool_end'
  | 'step_start'
  | 'step_complete'
  | 'error'
  | null {
  const mapping: Record<string, any> = {
    agent_created: 'agent_runtime_init',
    agent_runtime_end: 'agent_runtime_end',
    agent_runtime_init: 'agent_runtime_init',
    error: 'error',
    step_complete: 'step_complete',
    step_start: 'step_start',
    stream_chunk: 'stream_chunk',
    stream_end: 'stream_end',
    stream_start: 'stream_start',
    tool_end: 'tool_end',
    tool_start: 'tool_start',
  };
  return mapping[pythonType] ?? null;
}

/**
 * Start a background task that bridges a Python SSE stream into the TS
 * StreamEventManager for the given `operationId`.
 *
 * This function returns immediately — the bridging runs in the background.
 */
export function bridgePythonStream(
  operationId: string,
  userId: string,
  requestBody: unknown,
): void {
  // Fire-and-forget
  _runBridge(operationId, userId, requestBody).catch((err) => {
    log('Bridge failed for %s: %O', operationId, err);
  });
}

async function _runBridge(
  operationId: string,
  userId: string,
  requestBody: unknown,
): Promise<void> {
  let streamManager: IStreamEventManager;

  try {
    streamManager = createStreamEventManager();
  } catch {
    log('StreamEventManager unavailable — cannot bridge for %s', operationId);
    return;
  }

  const controller = new AbortController();

  let response: Response;
  try {
    response = await callPythonBackendStream('/api/ai-agent/exec/stream', userId, {
      body: requestBody,
      signal: controller.signal,
    });
  } catch (error) {
    log('Failed to connect to Python stream for %s: %O', operationId, error);
    await streamManager.publishStreamEvent(operationId, {
      data: { error: String(error) },
      stepIndex: 0,
      type: 'error',
    });
    await streamManager.publishAgentRuntimeEnd(operationId, 0, { error }, 'error');
    return;
  }

  if (!response.body) {
    log('Python stream response has no body for %s', operationId);
    return;
  }

  log('Bridge started for %s', operationId);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let stepIndex = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by double newlines
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || ''; // Last element is incomplete

      for (const frame of frames) {
        if (!frame.trim()) continue;

        const parsed = parseSSEFrame(frame);
        if (!parsed) continue;

        const eventType = mapEventType(parsed.event);
        if (!eventType) {
          log('Unmapped event type "%s" for %s', parsed.event, operationId);
          continue;
        }

        let eventData: any;
        try {
          eventData = JSON.parse(parsed.data);
        } catch {
          eventData = { raw: parsed.data };
        }

        // Track step index from the event data if available
        if (eventData.step_index !== undefined) {
          stepIndex = eventData.step_index;
        } else if (eventData.stepIndex !== undefined) {
          stepIndex = eventData.stepIndex;
        }

        await streamManager.publishStreamEvent(operationId, {
          data: eventData,
          stepIndex,
          type: eventType,
        });

        log('Bridged %s for %s (step %d)', eventType, operationId, stepIndex);

        // If runtime ended, stop reading
        if (eventType === 'agent_runtime_end') {
          controller.abort();
          break;
        }
      }
    }
  } catch (error) {
    if (controller.signal.aborted) {
      log('Bridge stream aborted for %s (expected after runtime end)', operationId);
    } else {
      log('Bridge stream error for %s: %O', operationId, error);
      await streamManager.publishStreamEvent(operationId, {
        data: { error: String(error) },
        stepIndex,
        type: 'error',
      });
      await streamManager.publishAgentRuntimeEnd(operationId, stepIndex, { error }, 'error');
    }
  } finally {
    reader.releaseLock();
    log('Bridge completed for %s', operationId);
  }
}
