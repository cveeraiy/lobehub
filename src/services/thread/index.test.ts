import { ThreadStatus } from '@lobechat/types';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { threadService } from './index';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('ThreadService REST', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes thread list responses', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce([
      {
        agent_id: 'agent-1',
        created_at: '2026-05-01T10:00:00.000Z',
        group_id: 'group-1',
        id: 'thread-1',
        last_active_at: '2026-05-01T10:02:00.000Z',
        metadata: { operationId: 'op-1' },
        parent_thread_id: 'parent-1',
        source_message_id: 'message-1',
        status: ThreadStatus.Processing,
        title: 'Thread',
        topic_id: 'topic-1',
        type: 'isolation',
        updated_at: '2026-05-01T10:01:00.000Z',
        user_id: 'user-1',
      },
    ]);

    const result = await threadService.getThreads('topic-1');

    expect(restClient.get).toHaveBeenCalledWith('/threads', {
      params: { topic_id: 'topic-1' },
    });
    expect(result[0]).toMatchObject({
      agentId: 'agent-1',
      groupId: 'group-1',
      id: 'thread-1',
      metadata: { operationId: 'op-1' },
      parentThreadId: 'parent-1',
      sourceMessageId: 'message-1',
      status: ThreadStatus.Processing,
      title: 'Thread',
      topicId: 'topic-1',
      type: 'isolation',
      userId: 'user-1',
    });
    expect(result[0].createdAt).toBeInstanceOf(Date);
    expect(result[0].lastActiveAt).toBeInstanceOf(Date);
    expect(result[0].updatedAt).toBeInstanceOf(Date);
  });

  it('creates a thread with message using Python endpoint shape', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({
      message_id: 'message-1',
      thread_id: 'thread-1',
    });

    const result = await threadService.createThreadWithMessage({
      message: {
        agentId: 'agent-1',
        content: 'hello',
        role: 'user',
        sessionId: 'inbox',
      },
      sourceMessageId: 'source-1',
      status: ThreadStatus.Active,
      title: 'Thread',
      topicId: 'topic-1',
      type: 'standalone',
    });

    expect(restClient.post).toHaveBeenCalledWith('/threads/with-message', {
      body: {
        agent_id: undefined,
        group_id: undefined,
        id: undefined,
        message: expect.objectContaining({
          agent_id: 'agent-1',
          content: 'hello',
          role: 'user',
          session_id: null,
        }),
        metadata: undefined,
        parent_thread_id: undefined,
        source_message_id: 'source-1',
        status: ThreadStatus.Active,
        title: 'Thread',
        topic_id: 'topic-1',
        type: 'standalone',
      },
    });
    expect(result).toEqual({ messageId: 'message-1', threadId: 'thread-1' });
  });

  it('creates and updates threads with snake_case request fields', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({ id: 'thread-1' });
    vi.mocked(restClient.put).mockResolvedValueOnce({ ok: true });

    const id = await threadService.createThread({
      agentId: 'agent-1',
      groupId: 'group-1',
      metadata: { clientMode: true },
      status: ThreadStatus.Pending,
      title: 'Thread',
      topicId: 'topic-1',
      type: 'isolation',
    });
    await threadService.updateThread('thread-1', {
      metadata: { completedAt: 'now' },
      status: ThreadStatus.Completed,
      title: 'Done',
    });

    expect(id).toBe('thread-1');
    expect(restClient.post).toHaveBeenCalledWith('/threads', {
      body: expect.objectContaining({
        agent_id: 'agent-1',
        group_id: 'group-1',
        metadata: { clientMode: true },
        status: ThreadStatus.Pending,
        topic_id: 'topic-1',
      }),
    });
    expect(restClient.put).toHaveBeenCalledWith('/threads/thread-1', {
      body: expect.objectContaining({
        metadata: { completedAt: 'now' },
        status: ThreadStatus.Completed,
        title: 'Done',
      }),
    });
  });
});
