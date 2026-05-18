import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { apiKeyService as restService } from './apiKey.rest';

const trpcService = {
  createApiKey: lambdaClient.apiKey.createApiKey.mutate,
  deleteApiKey: async (id: string): Promise<void> => {
    await lambdaClient.apiKey.deleteApiKey.mutate({ id });
  },
  getApiKeys: lambdaClient.apiKey.getApiKeys.query,
  updateApiKey: (id: string, params: Parameters<typeof restService.updateApiKey>[1]) =>
    lambdaClient.apiKey.updateApiKey.mutate({ id, value: params }),
};

export const apiKeyService = (
  shouldUseRest('apiKey') ? restService : trpcService
) as typeof restService;
