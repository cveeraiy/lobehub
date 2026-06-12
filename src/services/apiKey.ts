import { restClient } from '@/libs/rest';
import type { ApiKeyItem, CreateApiKeyParams, UpdateApiKeyParams } from '@/types/apiKey';

type ApiKeyResponse = Omit<
  ApiKeyItem,
  'accessedAt' | 'createdAt' | 'expiresAt' | 'lastUsedAt' | 'updatedAt'
> & {
  accessedAt?: Date | string | null;
  createdAt?: Date | string | null;
  expiresAt?: Date | string | null;
  lastUsedAt?: Date | string | null;
  updatedAt?: Date | string | null;
};

const toDate = (value?: Date | string | null) => (value ? new Date(value) : null);

const toApiKey = (item: ApiKeyResponse): ApiKeyItem => ({
  ...item,
  accessedAt: toDate(item.accessedAt) ?? toDate(item.lastUsedAt) ?? new Date(0),
  createdAt: toDate(item.createdAt) ?? new Date(),
  expiresAt: toDate(item.expiresAt),
  lastUsedAt: toDate(item.lastUsedAt),
  updatedAt: toDate(item.updatedAt) ?? new Date(),
});

class ApiKeyService {
  createApiKey = async (params: CreateApiKeyParams) => {
    return restClient.post<ApiKeyResponse>('/api-keys', {
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
    const items = await restClient.get<ApiKeyResponse[]>('/api-keys');
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
