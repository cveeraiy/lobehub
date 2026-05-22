import { INBOX_SESSION_ID } from '@/const/session';
import { restClient } from '@/libs/rest';
import type { BatchTaskResult } from '@/types/service';
import type {
  ChatTopic,
  ChatTopicMetadata,
  CreateTopicParams,
  QueryTopicParams,
  RecentTopic,
  TopicRankItem,
} from '@/types/topic';

type OnboardingSessionMetadataPatch = Partial<NonNullable<ChatTopicMetadata['onboardingSession']>>;

type UpdateTopicMetadataInput = Omit<Partial<ChatTopicMetadata>, 'onboardingSession'> & {
  onboardingSession?: OnboardingSessionMetadataPatch;
};

interface RawTopic {
  agent_id?: string | null;
  created_at?: string | null;
  favorite?: boolean;
  history_summary?: string | null;
  id: string;
  metadata?: ChatTopicMetadata | null;
  session_id?: string | null;
  status?: ChatTopic['status'] | null;
  title?: string | null;
  updated_at?: string | null;
}

interface RawTopicRankItem {
  id: string;
  message_count?: number;
  session_id?: string | null;
  title?: string | null;
}

const toTimestamp = (value?: string | null) => (value ? new Date(value).getTime() : 0);

const toTopic = (topic: RawTopic): ChatTopic => ({
  createdAt: toTimestamp(topic.created_at),
  favorite: topic.favorite,
  historySummary: topic.history_summary ?? undefined,
  id: topic.id,
  metadata: topic.metadata ?? undefined,
  sessionId: topic.session_id ?? undefined,
  status: topic.status,
  title: topic.title ?? '',
  updatedAt: toTimestamp(topic.updated_at),
});

const toTopicBody = (topic: Partial<ChatTopic>) => ({
  favorite: topic.favorite,
  history_summary: topic.historySummary,
  metadata: topic.metadata,
  session_id: topic.sessionId,
  status: topic.status,
  title: topic.title,
});

const toCreateTopicBody = (params: CreateTopicParams) => ({
  agent_id: undefined,
  favorite: params.favorite,
  group_id: params.groupId,
  session_id: params.sessionId,
  title: params.title,
  trigger: params.trigger,
});

export class TopicService {
  createTopic = async (params: CreateTopicParams): Promise<string> => {
    const res = await restClient.post<{ id: string }>('/topics', {
      body: toCreateTopicBody({ ...params, sessionId: this.toDbSessionId(params.sessionId) }),
    });
    return res.id;
  };

  batchCreateTopics = (importTopics: ChatTopic[]): Promise<BatchTaskResult> => {
    return restClient.post<BatchTaskResult>('/topics/batch', {
      body: { topics: importTopics.map(toTopicBody) },
    });
  };

  cloneTopic = async (id: string, newTitle?: string): Promise<string> => {
    const res = await restClient.post<{ id: string }>(`/topics/${id}/clone`, {
      body: { new_title: newTitle },
    });
    return res.id;
  };

  importTopic = (params: {
    agentId: string;
    data: string;
    groupId?: string | null;
  }): Promise<{ messageCount: number; topicId: string }> => {
    return restClient
      .post<{ id: string; message_count?: number }>('/topics/import', {
        body: { agent_id: params.agentId, data: params.data, group_id: params.groupId },
      })
      .then((result) => ({ messageCount: result.message_count ?? 0, topicId: result.id }));
  };

  getTopics = async (params: QueryTopicParams): Promise<{ items: ChatTopic[]; total: number }> => {
    const topics = await restClient.get<RawTopic[]>('/topics', {
      params: {
        agent_id: params.agentId ?? undefined,
        current: params.current,
        group_id: params.groupId ?? undefined,
        is_inbox: params.isInbox,
        page_size: params.pageSize,
      },
    });

    const items = topics.map(toTopic);
    return { items, total: items.length };
  };

  getAllTopics = (): Promise<ChatTopic[]> => {
    return restClient.get<RawTopic[]>('/topics/all').then((topics) => topics.map(toTopic));
  };

  countTopics = async (params?: {
    agentId?: string;
    containerId?: string | null;
    endDate?: string;
    range?: [string, string];
    startDate?: string;
  }): Promise<number> => {
    const res = await restClient.get<{ count: number }>('/topics/count', {
      params: {
        agent_id: params?.agentId,
        container_id: params?.containerId ?? undefined,
        end_date: params?.endDate,
        start_date: params?.startDate,
      },
    });
    return res.count;
  };

  rankTopics = async (limit?: number): Promise<TopicRankItem[]> => {
    const items = await restClient.get<RawTopicRankItem[]>('/topics/rank', {
      params: limit ? { limit } : undefined,
    });
    return items.map((item) => ({
      count: item.message_count ?? 0,
      id: item.id,
      sessionId: item.session_id ?? null,
      title: item.title ?? null,
    }));
  };

  getRecentTopics = async (limit?: number): Promise<RecentTopic[]> => {
    return restClient.get<RecentTopic[]>('/recent', {
      params: limit ? { limit } : undefined,
    });
  };

  getCronTopicsGroupedByCronJob = async (
    agentId: string,
  ): Promise<Array<{ cronJobId: string; topics: ChatTopic[] }>> => {
    const groups = await restClient.get<Array<{ cronJobId: string; topics: RawTopic[] }>>(
      '/topics/cron-grouped',
      {
        params: { agent_id: agentId },
      },
    );

    return groups.map((group) => ({
      cronJobId: group.cronJobId,
      topics: group.topics.map(toTopic),
    }));
  };

  getTopicContext = async (topicId: string): Promise<{ content: string; success: boolean }> => {
    const result = await restClient.get<{ message_count: number; topic: RawTopic }>(
      `/topics/${topicId}/context`,
    );
    return {
      content: `Topic: ${result.topic.title ?? 'Untitled'}\nMessages: ${result.message_count}`,
      success: true,
    };
  };

  searchTopics = (keywords: string, agentId?: string, groupId?: string): Promise<ChatTopic[]> => {
    return restClient
      .get<RawTopic[]>('/topics/search', {
        params: { agent_id: agentId, group_id: groupId, keywords },
      })
      .then((topics) => topics.map(toTopic));
  };

  updateTopic = (id: string, data: Partial<ChatTopic>) => {
    return restClient.put(`/topics/${id}`, { body: toTopicBody(data) });
  };

  updateTopicMetadata = (id: string, metadata: UpdateTopicMetadataInput) => {
    return restClient.put(`/topics/${id}`, { body: { metadata } });
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
