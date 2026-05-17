import { type CreateMessageParams } from '@lobechat/types';

import { INBOX_SESSION_ID } from '@/const/session';
import { restClient } from '@/libs/rest';
import { type CreateThreadParams, type ThreadItem } from '@/types/topic';

interface CreateThreadWithMessageParams extends CreateThreadParams {
  message: CreateMessageParams;
}

export class ThreadService {
  getThreads = (topicId: string): Promise<ThreadItem[]> => {
    return restClient.get<ThreadItem[]>('/threads', { params: { topic_id: topicId } });
  };

  createThreadWithMessage = async ({
    message,
    ...params
  }: CreateThreadWithMessageParams): Promise<{ messageId: string; threadId: string }> => {
    return restClient.post('/threads', {
      body: {
        ...params,
        message: { ...message, sessionId: this.toDbSessionId(message.sessionId) },
      },
    });
  };

  createThread = async (params: CreateThreadParams): Promise<string> => {
    const res = await restClient.post<{ id: string }>('/threads', { body: params });
    return res.id;
  };

  updateThread = async (id: string, data: Partial<ThreadItem>) => {
    return restClient.put(`/threads/${id}`, { body: data });
  };

  removeThread = async (id: string) => {
    return restClient.delete(`/threads/${id}`);
  };

  private toDbSessionId = (sessionId: string | undefined) => {
    return sessionId === INBOX_SESSION_ID ? null : sessionId;
  };
}

export const threadService = new ThreadService();
