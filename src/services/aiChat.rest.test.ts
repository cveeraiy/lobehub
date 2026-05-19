import { beforeEach, describe, expect, it, vi } from 'vitest';

import { aiChatService } from './aiChat.rest';

const mockRestPost = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    post: mockRestPost,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AiChatService REST', () => {
  it('sends server message creation payloads with Python field names', async () => {
    mockRestPost.mockResolvedValueOnce({
      assistantMessageId: 'assistant-1',
      userMessageId: 'user-1',
    });
    const abortController = new AbortController();

    await aiChatService.sendMessageInServer(
      {
        agentId: 'agent-1',
        newAssistantMessage: {
          model: 'gpt-4o',
          provider: 'openai',
        },
        newThread: {
          sourceMessageId: 'source-1',
          title: 'Thread',
          type: 'standalone',
        },
        newTopic: {
          title: 'Topic',
          topicMessageIds: ['message-1'],
        },
        newUserMessage: {
          content: 'Hello',
          editorData: { type: 'doc' },
          files: ['file-1'],
          parentId: 'parent-1',
        },
        sessionId: 'session-1',
        topicId: 'topic-1',
      },
      abortController,
    );

    expect(mockRestPost).toHaveBeenCalledWith('/ai-chat/send-message', {
      body: expect.objectContaining({
        agent_id: 'agent-1',
        new_assistant_message: {
          model: 'gpt-4o',
          provider: 'openai',
        },
        new_thread: expect.objectContaining({
          source_message_id: 'source-1',
        }),
        new_topic: expect.objectContaining({
          topic_message_ids: ['message-1'],
        }),
        new_user_message: expect.objectContaining({
          editor_data: { type: 'doc' },
          files: [{ id: 'file-1' }],
          parent_id: 'parent-1',
        }),
        session_id: 'session-1',
        topic_id: 'topic-1',
      }),
      signal: abortController.signal,
    });
  });

  it('normalizes Python message fields in the send response', async () => {
    mockRestPost.mockResolvedValueOnce({
      assistantMessageId: 'assistant-1',
      messages: [
        {
          agent_id: 'agent-1',
          content: 'Hello',
          created_at: '2026-05-18T12:00:00',
          id: 'message-1',
          parent_id: 'parent-1',
          role: 'user',
          topic_id: 'topic-1',
          updated_at: '2026-05-18T12:00:01',
        },
      ],
      topicId: 'topic-1',
      userMessageId: 'message-1',
    });

    const result = await aiChatService.sendMessageInServer(
      {
        agentId: 'agent-1',
        newAssistantMessage: {},
        newUserMessage: { content: 'Hello' },
      },
      new AbortController(),
    );

    expect(result.messages).toEqual([
      expect.objectContaining({
        agentId: 'agent-1',
        content: 'Hello',
        id: 'message-1',
        parentId: 'parent-1',
        topicId: 'topic-1',
      }),
    ]);
  });
});
