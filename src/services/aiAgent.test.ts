import { beforeEach, describe, expect, it, vi } from 'vitest';

import { aiAgentService } from './aiAgent';

const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
    post: mockRestPost,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AiAgentService REST', () => {
  it('executes group agents through the REST endpoint with snake_case fields', async () => {
    mockRestPost.mockResolvedValueOnce({
      assistant_message_id: 'assistant-1',
      is_create_new_topic: true,
      operation_id: 'operation-1',
      success: true,
      topic_id: 'topic-1',
      user_message_id: 'user-1',
    });

    const result = await aiAgentService.execGroupAgent({
      agentId: 'agent-1',
      files: ['file-1'],
      groupId: 'group-1',
      message: 'Run the group',
      topicId: null,
    });

    expect(result).toMatchObject({
      assistantMessageId: 'assistant-1',
      isCreateNewTopic: true,
      operationId: 'operation-1',
      topicId: 'topic-1',
      userMessageId: 'user-1',
    });
    expect(mockRestPost).toHaveBeenCalledWith('/ai-agent/exec-group', {
      body: {
        agent_id: 'agent-1',
        file_ids: ['file-1'],
        group_id: 'group-1',
        message: 'Run the group',
        new_topic: undefined,
        topic_id: undefined,
      },
      signal: undefined,
    });
  });

  it('executes agent tasks with nested app context and resume approval mapping', async () => {
    mockRestPost.mockResolvedValueOnce({
      operation_id: 'operation-1',
      status: 'created',
      success: true,
      topic_id: 'topic-1',
      user_message_id: 'user-1',
    });

    await aiAgentService.execAgentTask({
      agentId: 'agent-1',
      appContext: { groupId: 'group-1', topicId: 'topic-1' },
      prompt: 'Continue',
      resumeApproval: {
        decision: 'approved',
        parentMessageId: 'tool-message-1',
        toolCallId: 'tool-call-1',
      },
    });

    expect(mockRestPost).toHaveBeenCalledWith('/ai-agent/exec', {
      body: expect.objectContaining({
        agent_id: 'agent-1',
        app_context: expect.objectContaining({
          group_id: 'group-1',
          topic_id: 'topic-1',
        }),
        resume_approval: {
          decision: 'approved',
          parent_message_id: 'tool-message-1',
          rejection_reason: undefined,
          tool_call_id: 'tool-call-1',
        },
      }),
    });
  });

  it('maps client task thread payloads to Python field names', async () => {
    mockRestPost.mockResolvedValueOnce({ threadId: 'thread-1' });

    await aiAgentService.createClientGroupAgentTaskThread({
      groupId: 'group-1',
      instruction: 'Do work',
      parentMessageId: 'parent-1',
      subAgentId: 'agent-2',
      topicId: 'topic-1',
    });

    expect(mockRestPost).toHaveBeenCalledWith('/ai-agent/create-client-group-agent-task-thread', {
      body: {
        group_id: 'group-1',
        instruction: 'Do work',
        parent_message_id: 'parent-1',
        sub_agent_id: 'agent-2',
        title: undefined,
        topic_id: 'topic-1',
      },
    });
  });
});
