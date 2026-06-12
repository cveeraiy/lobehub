import { beforeEach, describe, expect, it, vi } from 'vitest';

import { messageService } from './index';

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

describe('MessageService REST', () => {
  it('creates messages with snake_case context fields', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'message-1', messages: [] });

    const result = await messageService.createMessage({
      agentId: 'agent-1',
      content: 'Hello REST',
      parentId: 'parent-1',
      role: 'user',
      sessionId: 'session-1',
      threadId: 'thread-1',
      topicId: 'topic-1',
    });

    expect(result).toEqual({ id: 'message-1', messages: [] });
    expect(mockRestPost).toHaveBeenCalledWith('/messages', {
      body: expect.objectContaining({
        agent_id: 'agent-1',
        content: 'Hello REST',
        group_id: undefined,
        parent_id: 'parent-1',
        role: 'user',
        session_id: 'session-1',
        thread_id: 'thread-1',
        topic_id: 'topic-1',
      }),
    });
  });

  it('normalizes Python message fields for the UI contract', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        agent_id: 'agent-1',
        content: 'REST response',
        created_at: '2026-05-01T10:00:00.000Z',
        id: 'message-1',
        message_group_id: 'group-1',
        parent_id: 'parent-1',
        role: 'assistant',
        topic_id: 'topic-1',
        updated_at: '2026-05-01T10:01:00.000Z',
      },
    ]);

    const result = await messageService.getMessages({ agentId: 'agent-1', topicId: 'topic-1' });

    expect(result[0]).toMatchObject({
      agentId: 'agent-1',
      content: 'REST response',
      groupId: 'group-1',
      id: 'message-1',
      parentId: 'parent-1',
      role: 'assistant',
      topicId: 'topic-1',
    });
    expect(typeof result[0].createdAt).toBe('number');
    expect(mockRestGet).toHaveBeenCalledWith('/messages', {
      params: {
        agent_id: 'agent-1',
        group_id: undefined,
        thread_id: undefined,
        topic_id: 'topic-1',
        topic_share_id: undefined,
      },
    });
  });

  it('updates message fields without TRPC value wrappers', async () => {
    mockRestPut.mockResolvedValueOnce({ ok: true });

    await messageService.updateMessage('message-1', {
      content: 'Edited',
      model: 'gpt-4o',
      provider: 'openai',
    });

    expect(mockRestPut).toHaveBeenCalledWith('/messages/message-1', {
      body: {
        content: 'Edited',
        error: undefined,
        model: 'gpt-4o',
        provider: 'openai',
        tools: undefined,
      },
      params: {
        agent_id: undefined,
        group_id: undefined,
        thread_id: undefined,
        topic_id: undefined,
        topic_share_id: undefined,
      },
    });
  });

  it('uses REST bulk delete and count-words response shapes', async () => {
    mockRestPost.mockResolvedValueOnce({ ok: true });
    mockRestGet.mockResolvedValueOnce({ words: 42 });

    await messageService.removeAllMessages();
    await expect(messageService.countWords()).resolves.toBe(42);

    expect(mockRestPost).toHaveBeenCalledWith('/messages/remove-all');
    expect(mockRestGet).toHaveBeenCalledWith('/messages/count-words', { params: undefined });
  });
});
