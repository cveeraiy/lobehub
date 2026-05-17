import { type AgentItem, type LobeAgentConfig } from '@lobechat/types';
import { type PartialDeep } from 'type-fest';

import { restClient } from '@/libs/rest';

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

export interface CreateAgentParams {
  config?: PartialDeep<AgentItem>;
  groupId?: string;
}

export interface CreateAgentResult {
  agentId: string;
}

export interface CreateAgentOnlyParams {
  config?: PartialDeep<AgentItem>;
  groupId: string;
}

export interface CreateAgentOnlyResult {
  agentId: string;
}

class AgentService {
  checkByMarketIdentifier = async (marketIdentifier: string): Promise<boolean> => {
    return restClient.get<boolean>('/agents/check-market', {
      params: { marketIdentifier },
    });
  };

  getAgentByMarketIdentifier = async (marketIdentifier: string): Promise<string | null> => {
    return restClient.get('/agents/by-market', { params: { marketIdentifier } });
  };

  getAgentByForkedFromIdentifier = async (forkedFromIdentifier: string): Promise<string | null> => {
    return restClient.get('/agents/by-forked', { params: { forkedFromIdentifier } });
  };

  createAgent = async (params: CreateAgentParams): Promise<CreateAgentResult> => {
    const normalizedConfig = normalizeMarketAgentModel(params.config);
    return restClient.post<CreateAgentResult>('/agents', {
      body: { config: normalizedConfig, groupId: params.groupId },
    });
  };

  createAgentOnly = async (params: CreateAgentOnlyParams): Promise<CreateAgentOnlyResult> => {
    const normalizedConfig = normalizeMarketAgentModel(params.config);
    return restClient.post<CreateAgentOnlyResult>('/agents/virtual', {
      body: { config: normalizedConfig, groupId: params.groupId },
    });
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
    return restClient.put(`/agents/${agentId}/knowledge-bases/${knowledgeBaseId}`, {
      body: { enabled },
    });
  };

  createAgentFiles = async (agentId: string, fileIds: string[], enabled?: boolean) => {
    return restClient.post(`/agents/${agentId}/files`, { body: { enabled, fileIds } });
  };

  deleteAgentFile = async (agentId: string, fileId: string) => {
    return restClient.delete(`/agents/${agentId}/files/${fileId}`);
  };

  toggleFile = async (agentId: string, fileId: string, enabled?: boolean) => {
    return restClient.put(`/agents/${agentId}/files/${fileId}`, { body: { enabled } });
  };

  getFilesAndKnowledgeBases = async (agentId: string) => {
    return restClient.get(`/agents/${agentId}/knowledge`);
  };

  getAgentConfigById = async (agentId: string) => {
    return restClient.get(`/agents/${agentId}`);
  };

  /** @deprecated use getAgentConfigById instead */
  getSessionConfig = async (sessionId: string) => {
    return restClient.get(`/agents/by-session/${sessionId}/config`);
  };

  updateAgentConfig = async (
    agentId: string,
    config: PartialDeep<LobeAgentConfig>,
    signal?: AbortSignal,
  ) => {
    return restClient.put(`/agents/${agentId}`, { body: config, signal });
  };

  updateAgentMeta = async (agentId: string, meta: AgentMetaUpdate, signal?: AbortSignal) => {
    return restClient.put(`/agents/${agentId}`, { body: meta, signal });
  };

  getBuiltinAgent = async (slug: string) => {
    return restClient.get(`/agents/builtin/${slug}`);
  };

  removeAgent = async (agentId: string) => {
    return restClient.delete(`/agents/${agentId}`);
  };

  queryAgents = async (params?: { keyword?: string; limit?: number; offset?: number }) => {
    return restClient.get('/agents', { params: params as any });
  };

  updateAgentPinned = async (agentId: string, pinned: boolean) => {
    return restClient.put(`/agents/${agentId}/pinned`, { body: { pinned } });
  };

  duplicateAgent = async (
    agentId: string,
    newTitle?: string,
  ): Promise<{ agentId: string } | null> => {
    return restClient.post(`/agents/${agentId}/duplicate`, { body: { newTitle } });
  };
}

export const agentService = new AgentService();
