import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { credsService as restService } from './creds.rest';

const trpcService = {
  createFile: lambdaClient.market.creds.createFile.mutate,
  createKV: lambdaClient.market.creds.createKV.mutate,
  createOAuth: lambdaClient.market.creds.createOAuth.mutate,
  delete: async (id: number): Promise<void> => {
    await lambdaClient.market.creds.delete.mutate({ id });
  },
  deleteByKey: async (key: string): Promise<void> => {
    await lambdaClient.market.creds.deleteByKey.mutate({ key });
  },
  get: (id: number, params?: { decrypt?: boolean }) =>
    lambdaClient.market.creds.get.query({ id, ...params }),
  getByKey: (key: string, params?: { decrypt?: boolean }) =>
    lambdaClient.market.creds.getByKey.query({ key, ...params }),
  getSkillCredStatus: (skillIdentifier: string) =>
    lambdaClient.market.creds.getSkillCredStatus.query({ skillIdentifier }),
  inject: lambdaClient.market.creds.inject.mutate,
  list: lambdaClient.market.creds.list.query,
  listOAuthConnections: lambdaClient.market.creds.listOAuthConnections.query,
  update: (id: number, params: Record<string, unknown>) =>
    lambdaClient.market.creds.update.mutate({ id, ...params }),
  uploadFile: lambdaClient.market.creds.uploadFile.mutate,
};

export const credsService = (
  shouldUseRest('creds') ? restService : trpcService
) as typeof restService;
