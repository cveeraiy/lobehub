import { INBOX_SESSION_ID } from '@/const/session';
import { restClient } from '@/libs/rest';
import { type BatchTaskResult } from '@/types/service';
import {
  type ChatTopic,
  type CreateTopicParams,
  type QueryTopicParams,
  type RecentTopic,
  type TopicRankItem,
} from '@/types/topic';

export class TopicService {
  createTopic = async (params: CreateTopicParams): Promise<string> => {
    const res = await restClient.post<{ id: string }>('/topics', {
      body: { ...params, sessionId: this.toDbSessionId(params.sessionId) },
    });
    return res.id;
  };

  batchCreateTopics = (importTopics: ChatTopic[]): Promise<BatchTaskResult> => {
    return restClient.post<BatchTaskResult>('/topics/batch', { body: importTopics });
  };

  cloneTopic = async (id: string, newTitle?: string): Promise<string> => {
    const res = await restClient.post<{ id: string }>(`/topics/${id}/clone`, {
      body: { newTitle },
    });
    return res.id;
  };

  importTopic = (params: {
    agentId: string;
    data: string;
    groupId?: string | null;
  }): Promise<{ messageCount: number; topicId: string }> => {
    return restClient.post('/topics/import', { body: params });
  };

  getTopics = async (params: QueryTopicParams): Promise<{ items: ChatTopic[]; total: number }> => {
    return restClient.get('/topics', {
      params: {
        agent_id: params.agentId,
        current: params.current,
        group_id: params.groupId,
        is_inbox: params.isInbox,
        page_size: params.pageSize,
      } as any,
    });
  };

  getAllTopics = (): Promise<ChatTopic[]> => {
    return restClient.get<ChatTopic[]>('/topics/all');
  };

  countTopics = async (params?: {
    agentId?: string;
    containerId?: string | null;
    endDate?: string;
    range?: [string, string];
    startDate?: string;
  }): Promise<number> => {
    const res = await restClient.get<{ count: number }>('/topics/count', {
      params: params as any,
    });
    return res.count;
  };

  rankTopics = async (limit?: number): Promise<TopicRankItem[]> => {
    return restClient.get<TopicRankItem[]>('/topics/rank', {
      params: limit ? { limit } : undefined,
    });
  };

  getRecentTopics = async (limit?: number): Promise<RecentTopic[]> => {
    return restClient.get<RecentTopic[]>('/recent', {
      params: limit ? { limit } : undefined,
    });
  };

  searchTopics = (keywords: string, agentId?: string, groupId?: string): Promise<ChatTopic[]> => {
    return restClient.get<ChatTopic[]>('/topics', {
      params: { agent_id: agentId, group_id: groupId, q: keywords } as any,
    });
  };

  updateTopic = (id: string, data: Partial<ChatTopic>) => {
    return restClient.put(`/topics/${id}`, { body: data });
  };

  updateTopicMetadata = (id: string, metadata: Record<string, any>) => {
    return restClient.put(`/topics/${id}/metadata`, { body: metadata });
  };

  getShareInfo = (topicId: string) => {
    return restClient.get(`/topics/${topicId}/share`);
  };

  enableSharing = (topicId: string, visibility?: 'private' | 'link') => {
    return restClient.post(`/topics/${topicId}/share`, { body: { visibility } });
  };

  updateShareVisibility = (topicId: string, visibility: 'private' | 'link') => {
    return restClient.put(`/topics/${topicId}/share`, { body: { visibility } });
  };

  disableSharing = (topicId: string) => {
    return restClient.delete(`/topics/${topicId}/share`);
  };

  removeTopic = (id: string) => {
    return restClient.delete(`/topics/${id}`);
  };

  removeTopics = (sessionId: string) => {
    return restClient.delete('/topics', {
      params: { session_id: this.toDbSessionId(sessionId) as string },
    });
  };

  removeTopicsByAgentId = (agentId: string) => {
    return restClient.delete('/topics', { params: { agent_id: agentId } });
  };

  batchRemoveTopics = (topics: string[]) => {
    return restClient.post('/topics/batch-delete', { body: { ids: topics } });
  };

  removeAllTopic = () => {
    return restClient.delete('/topics');
  };

  private toDbSessionId = (sessionId?: string | null) =>
    sessionId === INBOX_SESSION_ID ? null : sessionId;
}

export const topicService = new TopicService();
