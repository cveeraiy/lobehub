import { beforeEach, describe, expect, it, vi } from 'vitest';

import { testService } from '~test-utils';

import { TopicService, topicService } from './index';

const mockRestDelete = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());
const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
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

describe('TopicService', () => {
  testService(TopicService, { checkAsync: false });

  it('creates topics with snake_case session id', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'topic-1' });

    const result = await topicService.createTopic({
      favorite: true,
      sessionId: 'session-1',
      title: 'REST Topic',
    });

    expect(result).toBe('topic-1');
    expect(mockRestPost).toHaveBeenCalledWith('/topics', {
      body: expect.objectContaining({
        favorite: true,
        session_id: 'session-1',
        title: 'REST Topic',
      }),
    });
  });

  it('wraps and normalizes topic list responses', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        created_at: '2026-05-01T10:00:00.000Z',
        favorite: false,
        history_summary: 'Summary',
        id: 'topic-1',
        session_id: 'session-1',
        title: 'REST Topic',
        updated_at: '2026-05-01T11:00:00.000Z',
      },
    ]);

    const result = await topicService.getTopics({ agentId: 'agent-1', current: 0, pageSize: 10 });

    expect(result.total).toBe(1);
    expect(result.items[0]).toMatchObject({
      historySummary: 'Summary',
      id: 'topic-1',
      sessionId: 'session-1',
      title: 'REST Topic',
    });
    expect(typeof result.items[0].createdAt).toBe('number');
  });

  it('updates topic metadata through the canonical topic update endpoint', async () => {
    mockRestPut.mockResolvedValueOnce({ ok: true });

    await topicService.updateTopicMetadata('topic-1', {
      runningOperation: { assistantMessageId: 'message-1', operationId: 'operation-1' },
    });

    expect(mockRestPut).toHaveBeenCalledWith('/topics/topic-1', {
      body: {
        metadata: {
          runningOperation: { assistantMessageId: 'message-1', operationId: 'operation-1' },
        },
      },
    });
  });

  it('normalizes clone and rank responses', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'topic-copy' });
    mockRestGet.mockResolvedValueOnce([
      { id: 'topic-1', message_count: 3, session_id: 'session-1' },
    ]);

    await expect(topicService.cloneTopic('topic-1', 'Copy')).resolves.toBe('topic-copy');
    await expect(topicService.rankTopics()).resolves.toEqual([
      { count: 3, id: 'topic-1', sessionId: 'session-1', title: null },
    ]);

    expect(mockRestPost).toHaveBeenCalledWith('/topics/topic-1/clone', {
      body: { new_title: 'Copy' },
    });
  });
});
