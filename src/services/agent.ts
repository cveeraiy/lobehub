import { DEFAULT_AGENT_CONFIG } from '@lobechat/const';
import type { AgentItem, KnowledgeItem, LobeAgentConfig } from '@lobechat/types';
import { cleanObject, merge } from '@lobechat/utils';
import type { PartialDeep } from 'type-fest';

import { restClient, RestClientError } from '@/libs/rest';

/**
 * Market agent model can be either a string or an object with model details
 */
type MarketAgentModel =
  | LobeAgentConfig['model']
  | {
      model: LobeAgentConfig['model'];
      parameters?: Partial<LobeAgentConfig['params']>;
      provider?: LobeAgentConfig['provider'];
    };

type AgentMetaUpdate = Partial<
  Pick<
    AgentItem,
    'avatar' | 'backgroundColor' | 'description' | 'marketIdentifier' | 'tags' | 'title'
  >
>;

type RawAgentItem = Partial<AgentItem> & {
  background_color?: string | null;
  chat_config?: AgentItem['chatConfig'] | null;
  created_at?: string | null;
  id: string;
  market_identifier?: string | null;
  opening_message?: string | null;
  opening_questions?: string[] | null;
  session_group_id?: string | null;
  system_role?: string | null;
  updated_at?: string | null;
};

type AgentConfigResult = LobeAgentConfig &
  Partial<Pick<AgentItem, 'createdAt' | 'id' | 'updatedAt'>>;

interface MarketCheckResponse {
  agent_id?: string | null;
  exists: boolean;
}

interface AgentIdResponse {
  agentId?: string;
  id?: string;
}

/**
 * Normalize market agent config to standard agent config.
 */
const normalizeMarketAgentModel = (config?: PartialDeep<AgentItem>): PartialDeep<AgentItem> => {
  if (!config) return {};

  const model = config.model as MarketAgentModel | undefined;

  if (typeof model !== 'object' || model === null) {
    return config;
  }

  const { model: modelName, provider: modelProvider, parameters } = model;
  const existingParams = (config.params ?? {}) as Record<string, any>;
  const mergedParams = { ...parameters, ...existingParams };

  return {
    ...config,
    model: modelName,
    params: Object.keys(mergedParams).length > 0 ? mergedParams : undefined,
    provider: config.provider ?? modelProvider,
  };
};

const mergeDefaultAgentConfig = (item: Partial<AgentItem>): AgentItem =>
  merge(DEFAULT_AGENT_CONFIG, cleanObject(item as Record<string, any>)) as AgentItem;

const toAgentItem = (item: RawAgentItem | null): AgentItem | null => {
  if (!item) return null;

  const {
    background_color,
    chat_config,
    created_at,
    market_identifier,
    opening_message,
    opening_questions,
    session_group_id,
    system_role,
    updated_at,
    ...rest
  } = item;

  return mergeDefaultAgentConfig({
    ...rest,
    backgroundColor: rest.backgroundColor ?? background_color,
    chatConfig: rest.chatConfig ?? chat_config ?? undefined,
    createdAt: rest.createdAt ?? (created_at ? new Date(created_at) : new Date(0)),
    marketIdentifier: rest.marketIdentifier ?? market_identifier,
    openingMessage: rest.openingMessage ?? opening_message ?? undefined,
    openingQuestions: rest.openingQuestions ?? opening_questions ?? undefined,
    sessionGroupId: rest.sessionGroupId ?? session_group_id,
    systemRole: rest.systemRole ?? system_role ?? undefined,
    updatedAt: rest.updatedAt ?? (updated_at ? new Date(updated_at) : new Date(0)),
    userId: rest.userId ?? '',
  });
};

const toAgentList = (items: RawAgentItem[]): AgentItem[] =>
  items.map((item) => toAgentItem(item)).filter((item): item is AgentItem => Boolean(item));

const toAgentBody = (config: PartialDeep<AgentItem> = {}) => ({
  avatar: config.avatar,
  background_color: config.backgroundColor,
  chat_config: config.chatConfig,
  description: config.description,
  market_identifier: config.marketIdentifier,
  model: typeof config.model === 'string' ? config.model : undefined,
  opening_message: config.openingMessage,
  opening_questions: config.openingQuestions,
  plugins: config.plugins,
  provider: config.provider,
  session_group_id: config.sessionGroupId,
  system_role: config.systemRole,
  tags: config.tags,
  title: config.title,
  tts: config.tts,
  virtual: config.virtual,
});

const createSlug = (title?: string | null) => {
  const now = Date.now();
  const prefix = title
    ?.toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, '-')
    .replaceAll(/^-|-$/g, '');

  return `${prefix || 'agent'}-${now}`;
};

const maybeNullOn404 = async <T>(request: Promise<T>): Promise<T | null> => {
  try {
    return await request;
  } catch (error) {
    if (error instanceof RestClientError && error.status === 404) return null;
    throw error;
  }
};

export interface CreateAgentParams {
  config?: PartialDeep<AgentItem> | Record<string, unknown>;
  groupId?: string;
}

export interface CreateAgentResult {
  agentId: string;
}

export interface CreateAgentOnlyParams {
  config?: PartialDeep<AgentItem> | Record<string, unknown>;
  groupId: string;
}

export interface CreateAgentOnlyResult {
  agentId: string;
}

class AgentService {
  checkByMarketIdentifier = async (marketIdentifier: string): Promise<boolean> => {
    const response = await restClient.get<MarketCheckResponse>('/agents/check-market', {
      params: { identifier: marketIdentifier },
    });

    return response.exists;
  };

  getAgentByMarketIdentifier = async (marketIdentifier: string): Promise<string | null> => {
    const response = await maybeNullOn404(
      restClient.get<RawAgentItem>(`/agents/by-market/${encodeURIComponent(marketIdentifier)}`),
    );

    return response?.id ?? null;
  };

  getAgentByForkedFromIdentifier = async (forkedFromIdentifier: string): Promise<string | null> => {
    const response = await maybeNullOn404(
      restClient.get<RawAgentItem>(
        `/agents/by-forked-from/${encodeURIComponent(forkedFromIdentifier)}`,
      ),
    );

    return response?.id ?? null;
  };

  createAgent = async (params: CreateAgentParams): Promise<CreateAgentResult> => {
    const normalizedConfig = normalizeMarketAgentModel(params.config as PartialDeep<AgentItem>);
    const body = toAgentBody({ ...normalizedConfig, sessionGroupId: params.groupId });
    const response = await restClient.post<AgentIdResponse>('/agents', {
      body: {
        ...body,
        slug: normalizedConfig.slug ?? createSlug(normalizedConfig.title),
      },
    });

    return { agentId: response.agentId ?? response.id! };
  };

  createAgentOnly = async (params: CreateAgentOnlyParams): Promise<CreateAgentOnlyResult> => {
    const normalizedConfig = normalizeMarketAgentModel(params.config as PartialDeep<AgentItem>);
    const response = await restClient.post<AgentIdResponse>('/agents/virtual', {
      body: {
        ...toAgentBody({ ...normalizedConfig, virtual: true }),
        group_id: params.groupId,
        slug: normalizedConfig.slug ?? createSlug(normalizedConfig.title),
      },
    });

    return { agentId: response.agentId ?? response.id! };
  };

  createAgentKnowledgeBase = async (
    agentId: string,
    knowledgeBaseId: string,
    enabled?: boolean,
  ) => {
    return restClient.post(`/agents/${agentId}/knowledge-bases/${knowledgeBaseId}`, {
      body: { enabled },
    });
  };

  deleteAgentKnowledgeBase = async (agentId: string, knowledgeBaseId: string) => {
    return restClient.delete(`/agents/${agentId}/knowledge-bases/${knowledgeBaseId}`);
  };

  toggleKnowledgeBase = async (agentId: string, knowledgeBaseId: string, enabled?: boolean) => {
    return restClient.put(`/agents/${agentId}/knowledge-bases/${knowledgeBaseId}/toggle`, {
      params: { enabled },
    });
  };

  createAgentFiles = async (agentId: string, fileIds: string[], enabled?: boolean) => {
    return restClient.post(`/agents/${agentId}/files`, { body: { enabled, file_ids: fileIds } });
  };

  deleteAgentFile = async (agentId: string, fileId: string) => {
    return restClient.delete(`/agents/${agentId}/files/${fileId}`);
  };

  toggleFile = async (agentId: string, fileId: string, enabled?: boolean) => {
    return restClient.put(`/agents/${agentId}/files/${fileId}/toggle`, { params: { enabled } });
  };

  getFilesAndKnowledgeBases = async (agentId: string): Promise<KnowledgeItem[]> => {
    return restClient.get<KnowledgeItem[]>(`/agents/${agentId}/knowledge-and-files`);
  };

  getAgentConfigById = async (agentId: string): Promise<AgentConfigResult | null> => {
    return toAgentItem(
      await restClient.get<RawAgentItem | null>(`/agents/${agentId}`),
    ) as AgentConfigResult | null;
  };

  /** @deprecated use getAgentConfigById instead */
  getSessionConfig = async (sessionId: string): Promise<LobeAgentConfig> => {
    return restClient.get<LobeAgentConfig>(`/agents/config-by-session/${sessionId}`);
  };

  updateAgentConfig = async (
    agentId: string,
    config: PartialDeep<LobeAgentConfig>,
    signal?: AbortSignal,
  ) => {
    await restClient.put(`/agents/${agentId}`, { body: toAgentBody(config), signal });
    const agent = await this.getAgentConfigById(agentId);

    return { agent, success: true };
  };

  updateAgentMeta = async (agentId: string, meta: AgentMetaUpdate, signal?: AbortSignal) => {
    await restClient.put(`/agents/${agentId}`, { body: toAgentBody(meta), signal });
    const agent = await this.getAgentConfigById(agentId);

    return { agent, success: true };
  };

  getBuiltinAgent = async (slug: string) => {
    return toAgentItem(await restClient.get<RawAgentItem>(`/agents/builtin/${slug}`));
  };

  removeAgent = async (agentId: string) => {
    return restClient.delete(`/agents/${agentId}`);
  };

  queryAgents = async (params?: { keyword?: string; limit?: number; offset?: number }) => {
    const { keyword, ...rest } = params ?? {};
    const response = await restClient.get<RawAgentItem[]>('/agents/query', {
      params: { ...rest, keywords: keyword },
    });

    return toAgentList(response) as Array<{
      avatar: string | null;
      backgroundColor: string | null;
      description: string | null;
      id: string;
      title: string | null;
    }>;
  };

  updateAgentPinned = async (agentId: string, pinned: boolean) => {
    return restClient.put(`/agents/${agentId}/pinned`, { params: { pinned } });
  };

  duplicateAgent = async (
    agentId: string,
    newTitle?: string,
  ): Promise<{ agentId: string } | null> => {
    const response = await restClient.post<AgentIdResponse>(`/agents/${agentId}/duplicate`, {
      body: { new_title: newTitle },
    });

    const newAgentId = response.agentId ?? response.id;
    return newAgentId ? { agentId: newAgentId } : null;
  };
}

export const agentService = new AgentService();
