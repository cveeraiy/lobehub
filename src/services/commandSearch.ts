import { restClient } from '@/libs/rest';
import type { SearchResult } from '@/types/search';

interface RestSearchResponse {
  agents?: Array<{ description?: string | null; id: string; title?: string | null }>;
  messages?: Array<{
    content?: string | null;
    created_at?: string | null;
    id: string;
    session_id?: string | null;
  }>;
  topics?: Array<{
    created_at?: string | null;
    id: string;
    session_id?: string | null;
    title?: string | null;
  }>;
}

class CommandSearchService {
  query = async (params: {
    agentId?: string;
    limitPerType?: number;
    locale?: string;
    query: string;
    type?: string;
  }): Promise<SearchResult[]> => {
    const result = await restClient.get<RestSearchResponse>('/search', {
      params: {
        limit: params.limitPerType,
        q: params.query,
      },
    });
    const now = new Date();
    const messages =
      params.type && params.type !== 'message'
        ? []
        : (result.messages ?? []).map(
            (item) =>
              ({
                agentId: null,
                content: item.content ?? '',
                createdAt: item.created_at ? new Date(item.created_at) : now,
                id: item.id,
                model: null,
                relevance: 3,
                role: 'user',
                title: item.content ?? '',
                topicId: null,
                type: 'message',
                updatedAt: item.created_at ? new Date(item.created_at) : now,
              }) as SearchResult,
          );
    const topics =
      params.type && params.type !== 'topic'
        ? []
        : (result.topics ?? []).map(
            (item) =>
              ({
                agent: null,
                agentId: params.agentId ?? null,
                createdAt: item.created_at ? new Date(item.created_at) : now,
                favorite: null,
                id: item.id,
                relevance: 3,
                sessionId: item.session_id ?? null,
                title: item.title ?? '',
                type: 'topic',
                updatedAt: item.created_at ? new Date(item.created_at) : now,
              }) as SearchResult,
          );
    const agents =
      params.type && params.type !== 'agent'
        ? []
        : (result.agents ?? []).map(
            (item) =>
              ({
                avatar: null,
                backgroundColor: null,
                createdAt: now,
                description: item.description ?? null,
                id: item.id,
                relevance: 3,
                slug: null,
                tags: [],
                title: item.title ?? '',
                type: 'agent',
                updatedAt: now,
              }) as SearchResult,
          );

    return [...topics, ...messages, ...agents];
  };
}

export const commandSearchService = new CommandSearchService();
