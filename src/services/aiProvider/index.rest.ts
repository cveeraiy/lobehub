import { restClient } from '@/libs/rest';
import {
  type AiProviderDetailItem,
  type AiProviderRuntimeState,
  type AiProviderSortMap,
  type CreateAiProviderParams,
  type UpdateAiProviderConfigParams,
} from '@/types/aiProvider';

export class AiProviderService {
  createAiProvider = async (params: CreateAiProviderParams) => {
    return restClient.post('/ai-infra/providers', { body: params });
  };

  getAiProviderList = async () => {
    return restClient.get('/ai-infra/providers');
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
    return restClient.get<AiProviderRuntimeState>('/ai-infra/providers/runtime-state', {
      params: isLogin !== undefined ? { isLogin } : undefined,
    });
  };
}

export const aiProviderService = new AiProviderService();
