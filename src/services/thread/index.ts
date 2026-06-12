import type { CreateMessageParams } from '@lobechat/types';
import { ThreadStatus } from '@lobechat/types';

import { INBOX_SESSION_ID } from '@/const/session';
import { restClient } from '@/libs/rest';
import { type CreateThreadParams, type ThreadItem } from '@/types/topic';

interface CreateThreadWithMessageParams extends CreateThreadParams {
  message: CreateMessageParams;
}

interface RestThreadItem {
  agent_id?: string | null;
  created_at?: string | null;
  group_id?: string | null;
  id: string;
  last_active_at?: string | null;
  metadata?: ThreadItem['metadata'];
  parent_thread_id?: string | null;
  source_message_id?: string | null;
  status?: ThreadItem['status'];
  title?: string | null;
  topic_id: string;
  type?: ThreadItem['type'];
  updated_at?: string | null;
  user_id?: string;
}

const toDate = (value?: string | null) => (value ? new Date(value) : new Date());

const toThread = (thread: RestThreadItem): ThreadItem => ({
  agentId: thread.agent_id,
  createdAt: toDate(thread.created_at),
  groupId: thread.group_id,
  id: thread.id,
  lastActiveAt: toDate(thread.last_active_at ?? thread.updated_at ?? thread.created_at),
  metadata: thread.metadata,
  parentThreadId: thread.parent_thread_id ?? undefined,
  sourceMessageId: thread.source_message_id,
  status: thread.status ?? ThreadStatus.Active,
  title: thread.title ?? '',
  topicId: thread.topic_id,
  type: thread.type ?? 'standalone',
  updatedAt: toDate(thread.updated_at),
  userId: thread.user_id ?? '',
});

const toThreadBody = (params: Partial<CreateThreadParams | ThreadItem>) => ({
  agent_id: params.agentId,
  group_id: params.groupId,
  id: params.id,
  metadata: params.metadata,
  parent_thread_id: params.parentThreadId,
  source_message_id: params.sourceMessageId,
  status: params.status,
  title: params.title,
  topic_id: params.topicId,
  type: params.type,
});

const toMessageBody = (message: CreateMessageParams) => ({
  ...message,
  agent_id: message.agentId,
  session_id: message.sessionId === INBOX_SESSION_ID ? null : message.sessionId,
});

export class ThreadService {
  getThreads = async (topicId: string): Promise<ThreadItem[]> => {
    const threads = await restClient.get<RestThreadItem[]>('/threads', {
      params: { topic_id: topicId },
    });
    return threads.map(toThread);
  };

  createThreadWithMessage = async ({
    message,
    ...params
  }: CreateThreadWithMessageParams): Promise<{ messageId: string; threadId: string }> => {
    const result = await restClient.post<{ message_id: string; thread_id: string }>(
      '/threads/with-message',
      {
        body: {
          ...toThreadBody(params),
          message: toMessageBody(message),
        },
      },
    );
    return { messageId: result.message_id, threadId: result.thread_id };
  };

  createThread = async (params: CreateThreadParams): Promise<string> => {
    const res = await restClient.post<{ id: string }>('/threads', { body: toThreadBody(params) });
    return res.id;
  };

  updateThread = async (id: string, data: Partial<ThreadItem>) => {
    return restClient.put(`/threads/${id}`, { body: toThreadBody(data) });
  };

  removeThread = async (id: string) => {
    return restClient.delete(`/threads/${id}`);
  };
}

export const threadService = new ThreadService();
