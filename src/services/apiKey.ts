import { restClient } from '@/libs/rest';
import type { ApiKeyItem, CreateApiKeyParams, UpdateApiKeyParams } from '@/types/apiKey';

const toApiKey = (item: ApiKeyItem): ApiKeyItem => ({
  ...item,
  createdAt: item.createdAt ? new Date(item.createdAt) : new Date(),
  expiresAt: item.expiresAt ? new Date(item.expiresAt) : null,
  lastUsedAt: item.lastUsedAt ? new Date(item.lastUsedAt) : null,
  updatedAt: item.updatedAt ? new Date(item.updatedAt) : new Date(),
});

class ApiKeyService {
  createApiKey = async (params: CreateApiKeyParams) => {
    return restClient.post('/api-keys', {
      body: {
        expires_at: params.expiresAt,
        name: params.name,
      },
    });
  };

  deleteApiKey = async (id: string): Promise<void> => {
    await restClient.delete(`/api-keys/${id}`);
  };

  getApiKeys = async (): Promise<ApiKeyItem[]> => {
    const items = await restClient.get<ApiKeyItem[]>('/api-keys');
    return items.map(toApiKey);
  };

  updateApiKey = async (id: string, params: UpdateApiKeyParams) => {
    return restClient.put(`/api-keys/${id}`, {
      body: {
        enabled: params.enabled,
        expires_at: params.expiresAt,
        name: params.name,
      },
    });
  };
}

export const apiKeyService = new ApiKeyService();
