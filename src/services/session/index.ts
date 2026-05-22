import { DEFAULT_AGENT_CONFIG } from '@lobechat/const';
import type { PartialDeep } from 'type-fest';

import { restClient } from '@/libs/rest';
import type { LobeAgentChatConfig, LobeAgentConfig } from '@/types/agent';
import type { MetaData } from '@/types/meta';
import type {
  ChatSessionList,
  LobeAgentSession,
  LobeSession,
  LobeSessions,
  SessionGroupItem,
  SessionRankItem,
  UpdateSessionParams,
} from '@/types/session';
import { LobeSessionType } from '@/types/session';

interface RawSession {
  agent_id?: string | null;
  created_at?: string | null;
  group_id?: string | null;
  id: string;
  pinned?: boolean;
  slug?: string | null;
  type?: LobeSessionType;
  updated_at?: string | null;
}

interface RawSessionGroup {
  created_at?: string | null;
  id: string;
  name: string;
  sort?: number | null;
  updated_at?: string | null;
}

interface RawGroupedSessions {
  groups?: RawSessionGroup[];
  sessionGroups?: RawSessionGroup[];
  sessions: RawSession[] | Record<string, RawSession[]>;
}

const toDate = (value?: string | null) => (value ? new Date(value) : new Date(0));

const toSessionGroup = (group: RawSessionGroup): SessionGroupItem => ({
  createdAt: toDate(group.created_at),
  id: group.id,
  name: group.name,
  sort: group.sort,
  updatedAt: toDate(group.updated_at),
});

const toSession = (session: RawSession): LobeSession => {
  const base = {
    createdAt: toDate(session.created_at),
    group: session.group_id ?? undefined,
    id: session.id,
    meta: {},
    pinned: session.pinned,
    updatedAt: toDate(session.updated_at),
  };

  if (session.type === LobeSessionType.Group) {
    return { ...base, type: LobeSessionType.Group };
  }

  return {
    ...base,
    config: DEFAULT_AGENT_CONFIG,
    model: '',
    type: LobeSessionType.Agent,
  };
};

const toSessionList = (sessions: RawGroupedSessions['sessions']): LobeSessions => {
  const items = Array.isArray(sessions) ? sessions : Object.values(sessions).flat();
  return items.map(toSession);
};

const toGroupedSessions = (response: RawGroupedSessions): ChatSessionList => ({
  sessionGroups: (response.sessionGroups ?? response.groups ?? []).map(toSessionGroup),
  sessions: toSessionList(response.sessions),
});

const toSessionBody = (data: Partial<UpdateSessionParams>) => {
  const { group, meta, pinned, updatedAt } = data;

  return {
    group_id: group === 'default' ? null : group,
    pinned,
    updated_at: updatedAt,
    ...meta,
  };
};

const toAgentConfigBody = (config: PartialDeep<LobeAgentConfig>) => ({
  chat_config: config.chatConfig,
  model: config.model,
  provider: config.provider,
  system_role: config.systemRole,
});

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
    return restClient.get<RawGroupedSessions>('/sessions/grouped').then(toGroupedSessions);
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
      body: toSessionBody({ group, meta, pinned, updatedAt }),
    });
  };

  getSessionConfig = async (id: string): Promise<LobeAgentConfig> => {
    return restClient.get<LobeAgentConfig>(`/agents/config-by-session/${id}`);
  };

  updateSessionConfig = (
    id: string,
    config: PartialDeep<LobeAgentConfig>,
    signal?: AbortSignal,
  ) => {
    return restClient.put(`/sessions/${id}/config`, { body: toAgentConfigBody(config), signal });
  };

  updateSessionMeta = (id: string, meta: Partial<MetaData>, signal?: AbortSignal) => {
    return restClient.put(`/sessions/${id}/config`, { body: meta, signal });
  };

  updateSessionChatConfig = (
    id: string,
    value: Partial<LobeAgentChatConfig>,
    signal?: AbortSignal,
  ) => {
    return restClient.put(`/sessions/${id}/chat-config`, {
      body: { chat_config: value },
      signal,
    });
  };

  searchSessions = (keywords: string): Promise<LobeSessions> => {
    return restClient
      .get<RawSession[]>('/sessions/search', { params: { keywords } })
      .then((items) => items.map(toSession));
  };

  removeSession = (id: string) => {
    return restClient.delete(`/sessions/${id}`);
  };

  removeAllSessions = () => {
    return restClient.post('/sessions/remove-all');
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
    return restClient.post('/session-groups/remove-all');
  };

  updateSessionGroup = (id: string, value: Partial<SessionGroupItem>) => {
    return restClient.put(`/session-groups/${id}`, { body: value });
  };

  updateSessionGroupOrder = (sortMap: { id: string; sort: number }[]) => {
    return restClient.put('/session-groups/order', { body: { sortMap } });
  };
}

export const sessionService = new SessionService();
