import { type PartialDeep } from 'type-fest';

import { restClient } from '@/libs/rest';
import { type LobeAgentChatConfig, type LobeAgentConfig } from '@/types/agent';
import { type MetaData } from '@/types/meta';
import {
  type ChatSessionList,
  type LobeAgentSession,
  type LobeSessions,
  type LobeSessionType,
  type SessionGroupItem,
  type SessionRankItem,
  type UpdateSessionParams,
} from '@/types/session';

/**
 * @deprecated Session service is legacy. Use agentService for agent CRUD operations.
 */
export class SessionService {
  hasSessions = async (): Promise<boolean> => {
    const result = await this.countSessions();
    return result === 0;
  };

  /** @deprecated Use agentService.createAgent instead */
  createSession = async (
    type: LobeSessionType,
    data: Partial<LobeAgentSession>,
  ): Promise<string> => {
    const { config, group, meta, ...session } = data;
    const res = await restClient.post<{ id: string }>('/sessions', {
      body: {
        config: { ...config, ...meta },
        session: { ...session, groupId: group },
        type,
      },
    });
    return res.id;
  };

  cloneSession = async (id: string, newTitle: string): Promise<string | undefined> => {
    const res = await restClient.post<{ id?: string }>(`/sessions/${id}/clone`, {
      body: { newTitle },
    });
    return res.id;
  };

  getGroupedSessions = (): Promise<ChatSessionList> => {
    return restClient.get<ChatSessionList>('/sessions/grouped');
  };

  countSessions = async (params?: {
    endDate?: string;
    range?: [string, string];
    startDate?: string;
  }): Promise<number> => {
    const res = await restClient.get<{ count: number }>('/sessions/count', {
      params: params as any,
    });
    return res.count;
  };

  rankSessions = async (limit?: number): Promise<SessionRankItem[]> => {
    return restClient.get<SessionRankItem[]>('/sessions/rank', {
      params: limit ? { limit } : undefined,
    });
  };

  updateSession = (id: string, data: Partial<UpdateSessionParams>) => {
    const { group, pinned, meta, updatedAt } = data;
    return restClient.put(`/sessions/${id}`, {
      body: { groupId: group === 'default' ? null : group, pinned, ...meta, updatedAt },
    });
  };

  getSessionConfig = async (id: string): Promise<LobeAgentConfig> => {
    return restClient.get<LobeAgentConfig>(`/agents/by-session/${id}/config`);
  };

  updateSessionConfig = (
    id: string,
    config: PartialDeep<LobeAgentConfig>,
    signal?: AbortSignal,
  ) => {
    return restClient.put(`/sessions/${id}/config`, { body: config, signal });
  };

  updateSessionMeta = (id: string, meta: Partial<MetaData>, signal?: AbortSignal) => {
    return restClient.put(`/sessions/${id}/config`, { body: meta, signal });
  };

  updateSessionChatConfig = (
    id: string,
    value: Partial<LobeAgentChatConfig>,
    signal?: AbortSignal,
  ) => {
    return restClient.put(`/sessions/${id}/chat-config`, { body: value, signal });
  };

  searchSessions = (keywords: string): Promise<LobeSessions> => {
    return restClient.get<LobeSessions>('/sessions', { params: { q: keywords } });
  };

  removeSession = (id: string) => {
    return restClient.delete(`/sessions/${id}`);
  };

  removeAllSessions = () => {
    return restClient.delete('/sessions');
  };

  // ************************************** //
  // ***********  SessionGroup  *********** //
  // ************************************** //

  createSessionGroup = async (name: string, sort?: number): Promise<string> => {
    const res = await restClient.post<{ id: string }>('/session-groups', {
      body: { name, sort },
    });
    return res.id;
  };

  removeSessionGroup = (id: string, removeChildren?: boolean) => {
    return restClient.delete(`/session-groups/${id}`, {
      params: removeChildren ? { removeChildren: true } : undefined,
    });
  };

  removeSessionGroups = () => {
    return restClient.delete('/session-groups');
  };

  updateSessionGroup = (id: string, value: Partial<SessionGroupItem>) => {
    return restClient.put(`/session-groups/${id}`, { body: value });
  };

  updateSessionGroupOrder = (sortMap: { id: string; sort: number }[]) => {
    return restClient.put('/session-groups/order', { body: { sortMap } });
  };
}

export const sessionService = new SessionService();
