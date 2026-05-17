import { describe, expect, it, vi } from 'vitest';

import { bridgePythonStream } from './pythonStreamBridge';

const { mockPublishStreamEvent, mockPublishAgentRuntimeEnd, mockCallPythonBackendStream } =
  vi.hoisted(() => ({
    mockCallPythonBackendStream: vi.fn(),
    mockPublishAgentRuntimeEnd: vi.fn().mockResolvedValue('end-id'),
    mockPublishStreamEvent: vi.fn().mockResolvedValue('event-id'),
  }));

vi.mock('@/server/modules/AgentRuntime', () => ({
  createStreamEventManager: vi.fn(() => ({
    publishAgentRuntimeEnd: mockPublishAgentRuntimeEnd,
    publishStreamEvent: mockPublishStreamEvent,
  })),
}));

vi.mock('@/server/utils/pythonBackend', () => ({
  callPythonBackendStream: mockCallPythonBackendStream,
}));

/**
 * Helper to create a ReadableStream from SSE text frames.
 */
function createSSEStream(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
}

describe('bridgePythonStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('bridges SSE events to StreamEventManager', async () => {
    const sseFrames = [
      'event: agent_runtime_init\ndata: {"step_index":0,"message":"started"}\n\n',
      'event: stream_chunk\ndata: {"step_index":0,"content":"hello"}\n\n',
      'event: stream_end\ndata: {"step_index":0}\n\n',
      'event: agent_runtime_end\ndata: {"step_index":0,"reason":"completed"}\n\n',
    ];

    mockCallPythonBackendStream.mockResolvedValue({
      body: createSSEStream(sseFrames),
      ok: true,
    });

    bridgePythonStream('op-123', 'user-1', { prompt: 'test' });

    // Wait for the async bridge to complete
    await vi.waitFor(
      () => {
        expect(mockPublishStreamEvent).toHaveBeenCalledTimes(4);
      },
      { timeout: 2000 },
    );

    // Verify event types were mapped correctly
    expect(mockPublishStreamEvent).toHaveBeenCalledWith('op-123', {
      data: expect.objectContaining({ message: 'started' }),
      stepIndex: 0,
      type: 'agent_runtime_init',
    });

    expect(mockPublishStreamEvent).toHaveBeenCalledWith('op-123', {
      data: expect.objectContaining({ content: 'hello' }),
      stepIndex: 0,
      type: 'stream_chunk',
    });

    expect(mockPublishStreamEvent).toHaveBeenCalledWith('op-123', {
      data: expect.objectContaining({}),
      stepIndex: 0,
      type: 'stream_end',
    });

    expect(mockPublishStreamEvent).toHaveBeenCalledWith('op-123', {
      data: expect.objectContaining({ reason: 'completed' }),
      stepIndex: 0,
      type: 'agent_runtime_end',
    });
  });

  it('publishes error events when stream connection fails', async () => {
    mockCallPythonBackendStream.mockRejectedValue(new Error('Connection refused'));

    bridgePythonStream('op-fail', 'user-1', { prompt: 'test' });

    await vi.waitFor(
      () => {
        expect(mockPublishStreamEvent).toHaveBeenCalledWith('op-fail', {
          data: { error: 'Error: Connection refused' },
          stepIndex: 0,
          type: 'error',
        });
      },
      { timeout: 2000 },
    );

    expect(mockPublishAgentRuntimeEnd).toHaveBeenCalledWith(
      'op-fail',
      0,
      { error: expect.any(Error) },
      'error',
    );
  });

  it('handles empty body gracefully', async () => {
    mockCallPythonBackendStream.mockResolvedValue({
      body: null,
      ok: true,
    });

    bridgePythonStream('op-nobody', 'user-1', { prompt: 'test' });

    // Give it time to run
    await new Promise((r) => setTimeout(r, 100));

    // No events should be published (no body to read)
    expect(mockPublishStreamEvent).not.toHaveBeenCalled();
  });

  it('tracks step_index from event data', async () => {
    const sseFrames = [
      'event: step_start\ndata: {"step_index":0}\n\n',
      'event: stream_chunk\ndata: {"step_index":1,"content":"step1"}\n\n',
      'event: agent_runtime_end\ndata: {"step_index":2}\n\n',
    ];

    mockCallPythonBackendStream.mockResolvedValue({
      body: createSSEStream(sseFrames),
      ok: true,
    });

    bridgePythonStream('op-steps', 'user-1', { prompt: 'test' });

    await vi.waitFor(
      () => {
        expect(mockPublishStreamEvent).toHaveBeenCalledTimes(3);
      },
      { timeout: 2000 },
    );

    const calls = mockPublishStreamEvent.mock.calls;
    expect(calls[0][1].stepIndex).toBe(0);
    expect(calls[1][1].stepIndex).toBe(1);
    expect(calls[2][1].stepIndex).toBe(2);
  });

  it('skips unmapped event types', async () => {
    const sseFrames = [
      'event: unknown_event\ndata: {"foo":"bar"}\n\n',
      'event: stream_chunk\ndata: {"content":"hello"}\n\n',
      'event: agent_runtime_end\ndata: {}\n\n',
    ];

    mockCallPythonBackendStream.mockResolvedValue({
      body: createSSEStream(sseFrames),
      ok: true,
    });

    bridgePythonStream('op-skip', 'user-1', { prompt: 'test' });

    await vi.waitFor(
      () => {
        expect(mockPublishStreamEvent).toHaveBeenCalledTimes(2);
      },
      { timeout: 2000 },
    );

    // Only stream_chunk and agent_runtime_end should be published
    expect(mockPublishStreamEvent).toHaveBeenCalledWith(
      'op-skip',
      expect.objectContaining({ type: 'stream_chunk' }),
    );
    expect(mockPublishStreamEvent).toHaveBeenCalledWith(
      'op-skip',
      expect.objectContaining({ type: 'agent_runtime_end' }),
    );
  });
});
