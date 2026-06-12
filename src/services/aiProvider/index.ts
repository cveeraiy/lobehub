import { restClient } from '@/libs/rest';
import {
  type AiProviderDetailItem,
  type AiProviderListItem,
  type AiProviderRuntimeConfig,
  type AiProviderRuntimeState,
  type AiProviderSortMap,
  type CreateAiProviderParams,
  type EnabledProvider,
  type UpdateAiProviderConfigParams,
} from '@/types/aiProvider';

interface RestEnabledAiModel {
  abilities?: AiProviderRuntimeState['enabledAiModels'][number]['abilities'];
  config?: AiProviderRuntimeState['enabledAiModels'][number]['config'];
  context_window_tokens?: number;
  contextWindowTokens?: number;
  display_name?: string;
  displayName?: string;
  enabled?: boolean;
  id: string;
  parameters?: AiProviderRuntimeState['enabledAiModels'][number]['parameters'];
  provider_id?: string;
  providerId?: string;
  released_at?: string;
  releasedAt?: string;
  settings?: AiProviderRuntimeState['enabledAiModels'][number]['settings'];
  sort?: number;
  type: AiProviderRuntimeState['enabledAiModels'][number]['type'];
}

interface RestAiProviderRuntimeConfig {
  config?: AiProviderRuntimeConfig['config'];
  fetch_on_client?: boolean;
  fetchOnClient?: boolean;
  key_vaults?: AiProviderRuntimeConfig['keyVaults'];
  keyVaults?: AiProviderRuntimeConfig['keyVaults'];
  settings?: AiProviderRuntimeConfig['settings'];
}

interface RestAiProviderRuntimeState {
  enabledAiModels: RestEnabledAiModel[];
  enabledAiProviders: EnabledProvider[];
  enabledChatAiProviders: EnabledProvider[];
  enabledImageAiProviders?: EnabledProvider[];
  enabledVideoAiProviders?: EnabledProvider[];
  runtimeConfig?: Record<string, RestAiProviderRuntimeConfig>;
}

const normalizeRuntimeState = (data: RestAiProviderRuntimeState): AiProviderRuntimeState => ({
  enabledAiModels: data.enabledAiModels.map((model) => ({
    abilities: model.abilities || {},
    config: model.config,
    contextWindowTokens: model.contextWindowTokens ?? model.context_window_tokens,
    displayName: model.displayName ?? model.display_name,
    enabled: model.enabled,
    id: model.id,
    parameters: model.parameters,
    providerId: model.providerId ?? model.provider_id ?? '',
    releasedAt: model.releasedAt ?? model.released_at,
    settings: model.settings,
    sort: model.sort,
    type: model.type,
  })),
  enabledAiProviders: data.enabledAiProviders,
  enabledChatAiProviders: data.enabledChatAiProviders,
  enabledImageAiProviders: data.enabledImageAiProviders || [],
  enabledVideoAiProviders: data.enabledVideoAiProviders || [],
  runtimeConfig: Object.fromEntries(
    Object.entries(data.runtimeConfig || {}).map(([providerId, config]) => [
      providerId,
      {
        config: config.config || {},
        fetchOnClient: config.fetchOnClient ?? config.fetch_on_client,
        keyVaults: config.keyVaults ?? config.key_vaults ?? {},
        settings: config.settings || {},
      },
    ]),
  ),
});

export class AiProviderService {
  createAiProvider = async (params: CreateAiProviderParams): Promise<string> => {
    return restClient.post('/ai-infra/providers', { body: params });
  };

  getAiProviderList = async (): Promise<AiProviderListItem[]> => {
    return restClient.get<AiProviderListItem[]>('/ai-infra/providers');
  };

  getAiProviderById = async (id: string): Promise<AiProviderDetailItem | undefined> => {
    return restClient.get(`/ai-infra/providers/${id}`);
  };

  toggleProviderEnabled = async (id: string, enabled: boolean) => {
    return restClient.put(`/ai-infra/providers/${id}/toggle`, { body: { enabled } });
  };

  updateAiProvider = async (id: string, value: any) => {
    return restClient.put(`/ai-infra/providers/${id}`, { body: value });
  };

  updateAiProviderConfig = async (id: string, value: UpdateAiProviderConfigParams) => {
    return restClient.put(`/ai-infra/providers/${id}/config`, { body: value });
  };

  updateAiProviderOrder = async (items: AiProviderSortMap[]) => {
    return restClient.put('/ai-infra/providers/order', { body: { sortMap: items } });
  };

  deleteAiProvider = async (id: string) => {
    return restClient.delete(`/ai-infra/providers/${id}`);
  };

  getAiProviderRuntimeState = async (isLogin?: boolean): Promise<AiProviderRuntimeState> => {
    const data = await restClient.get<RestAiProviderRuntimeState>(
      '/ai-infra/providers/runtime-state',
      {
        params: isLogin !== undefined ? { isLogin } : undefined,
      },
    );
    return normalizeRuntimeState(data);
  };
}

export const aiProviderService = new AiProviderService();
