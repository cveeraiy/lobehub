import {
  type AiModelSortMap,
  type AiProviderModelListItem,
  type CreateAiModelParams,
  type ToggleAiModelEnableParams,
  type UpdateAiModelParams,
} from 'model-bank';

import { restClient } from '@/libs/rest';

export interface GetAiProviderModelListParams {
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

export class AiModelService {
  createAiModel = async (params: CreateAiModelParams) => {
    return restClient.post('/ai-infra/models', { body: params });
  };

  getAiProviderModelList = async (
    id: string,
    params?: GetAiProviderModelListParams,
  ): Promise<AiProviderModelListItem[]> => {
    return restClient.get<AiProviderModelListItem[]>(`/ai-infra/providers/${id}/models`, {
      params: params as any,
    });
  };

  getAiModelById = async (id: string) => {
    return restClient.get(`/ai-infra/models/${id}`);
  };

  toggleModelEnabled = async (params: ToggleAiModelEnableParams) => {
    return restClient.put('/ai-infra/models/toggle', { body: params });
  };

  updateAiModel = async (id: string, providerId: string, value: UpdateAiModelParams) => {
    return restClient.put(`/ai-infra/models/${id}`, { body: { providerId, value } });
  };

  batchUpdateAiModels = async (id: string, models: AiProviderModelListItem[]) => {
    return restClient.put(`/ai-infra/providers/${id}/models/batch`, { body: { models } });
  };

  batchToggleAiModels = async (id: string, models: string[], enabled: boolean) => {
    return restClient.put(`/ai-infra/providers/${id}/models/batch-toggle`, {
      body: { enabled, models },
    });
  };

  clearModelsByProvider = async (providerId: string) => {
    return restClient.delete(`/ai-infra/providers/${providerId}/models`);
  };

  clearRemoteModels = async (providerId: string) => {
    return restClient.delete(`/ai-infra/providers/${providerId}/remote-models`);
  };

  updateAiModelOrder = async (providerId: string, items: AiModelSortMap[]) => {
    return restClient.put(`/ai-infra/providers/${providerId}/models/order`, {
      body: { sortMap: items },
    });
  };

  deleteAiModel = async (params: { id: string; providerId: string }) => {
    return restClient.delete(`/ai-infra/models/${params.id}`, {
      params: { provider_id: params.providerId },
    });
  };
}

export const aiModelService = new AiModelService();
