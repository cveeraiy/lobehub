import { beforeEach, describe, expect, it, vi } from 'vitest';

import { agentService } from './agent.rest';

const mockRestDelete = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());
const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  RestClientError: class RestClientError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  restClient: {
    delete: mockRestDelete,
    get: mockRestGet,
    post: mockRestPost,
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AgentService REST', () => {
  it('creates agents with the Python router body shape and normalizes the id response', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'agent-1' });

    const result = await agentService.createAgent({
      config: {
        backgroundColor: '#fff',
        systemRole: 'Be concise',
        title: 'REST Agent',
      },
      groupId: 'group-1',
    });

    expect(result).toEqual({ agentId: 'agent-1' });
    expect(mockRestPost).toHaveBeenCalledWith('/agents', {
      body: expect.objectContaining({
        background_color: '#fff',
        session_group_id: 'group-1',
        slug: expect.stringMatching(/^rest-agent-\d+$/),
        system_role: 'Be concise',
        title: 'REST Agent',
      }),
    });
  });

  it('maps snake_case agent fields from REST responses to frontend fields', async () => {
    mockRestGet.mockResolvedValueOnce({
      background_color: '#000',
      chat_config: { enableHistoryCount: true },
      created_at: '2026-05-01T10:00:00.000Z',
      id: 'agent-1',
      market_identifier: 'market-agent',
      opening_message: 'Hello',
      opening_questions: ['Q1'],
      session_group_id: 'group-1',
      system_role: 'Answer well',
      title: 'REST Agent',
      updated_at: '2026-05-02T10:00:00.000Z',
    });

    const result = await agentService.getAgentConfigById('agent-1');

    expect(mockRestGet).toHaveBeenCalledWith('/agents/agent-1');
    expect(result).toMatchObject({
      backgroundColor: '#000',
      chatConfig: { enableHistoryCount: true },
      id: 'agent-1',
      marketIdentifier: 'market-agent',
      openingMessage: 'Hello',
      openingQuestions: ['Q1'],
      sessionGroupId: 'group-1',
      systemRole: 'Answer well',
      title: 'REST Agent',
    });
    expect(result?.createdAt).toBeInstanceOf(Date);
    expect(result?.updatedAt).toBeInstanceOf(Date);
  });

  it('updates agent meta with snake_case fields and returns the refreshed agent', async () => {
    mockRestPut.mockResolvedValueOnce({ ok: true });
    mockRestGet.mockResolvedValueOnce({
      background_color: '#123',
      id: 'agent-1',
      title: 'Renamed',
      updated_at: '2026-05-02T10:00:00.000Z',
    });

    const result = await agentService.updateAgentMeta('agent-1', {
      backgroundColor: '#123',
      title: 'Renamed',
    });

    expect(mockRestPut).toHaveBeenCalledWith('/agents/agent-1', {
      body: expect.objectContaining({
        background_color: '#123',
        title: 'Renamed',
      }),
      signal: undefined,
    });
    expect(result).toMatchObject({
      agent: { backgroundColor: '#123', id: 'agent-1', title: 'Renamed' },
      success: true,
    });
  });

  it('normalizes market check and duplicate responses', async () => {
    mockRestGet.mockResolvedValueOnce({ agent_id: null, exists: true });
    mockRestPost.mockResolvedValueOnce({ id: 'agent-copy' });

    await expect(agentService.checkByMarketIdentifier('market-agent')).resolves.toBe(true);
    await expect(agentService.duplicateAgent('agent-1', 'Copy title')).resolves.toEqual({
      agentId: 'agent-copy',
    });

    expect(mockRestGet).toHaveBeenCalledWith('/agents/check-market', {
      params: { identifier: 'market-agent' },
    });
    expect(mockRestPost).toHaveBeenCalledWith('/agents/agent-1/duplicate', {
      body: { new_title: 'Copy title' },
    });
  });
});
