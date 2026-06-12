import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import { agentSignalService } from '@/services/agentSignal';

vi.mock('@/libs/rest', () => ({
  restClient: {
    post: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AgentSignalService', () => {
  it('emits client source events through REST', async () => {
    const payload = {
      payload: { operationId: 'op-1' },
      sourceId: 'op-1',
      sourceType: 'client.runtime.start' as const,
    };

    await agentSignalService.emitSourceEvent(payload);

    expect(restClient.post).toHaveBeenCalledWith('/agent-signal/emit', { body: payload });
  });

  it('adds a timestamp for client gateway source events', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234);

    await agentSignalService.emitClientGatewaySourceEvent({
      payload: { operationId: 'op-1' },
      sourceId: 'op-1',
      sourceType: 'client.runtime.start',
    });

    expect(restClient.post).toHaveBeenCalledWith('/agent-signal/emit', {
      body: {
        payload: { operationId: 'op-1' },
        sourceId: 'op-1',
        sourceType: 'client.runtime.start',
        timestamp: 1234,
      },
    });
  });
});
