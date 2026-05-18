import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { oauthDeviceFlowService as restService } from './oauthDeviceFlow.rest';

const trpcService = {
  getAuthStatus: (providerId: string) =>
    lambdaClient.oauthDeviceFlow.getAuthStatus.query({ providerId }),
  initiateDeviceCode: (providerId: string) =>
    lambdaClient.oauthDeviceFlow.initiateDeviceCode.mutate({ providerId }),
  pollAuthStatus: (params: { deviceCode: string; providerId: string }) =>
    lambdaClient.oauthDeviceFlow.pollAuthStatus.mutate(params),
  revokeAuth: (providerId: string) =>
    lambdaClient.oauthDeviceFlow.revokeAuth.mutate({ providerId }),
};

export const oauthDeviceFlowService = shouldUseRest('oauthDeviceFlow') ? restService : trpcService;
