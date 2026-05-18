import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { klavisService as restService } from './klavis.rest';

const trpcService = {
  createServerInstance: lambdaClient.klavis.createServerInstance.mutate,
  deleteServerInstance: lambdaClient.klavis.deleteServerInstance.mutate,
  getKlavisPlugins: lambdaClient.klavis.getKlavisPlugins.query,
  getServerInstance: lambdaClient.klavis.getServerInstance.query,
  removeKlavisPlugin: lambdaClient.klavis.removeKlavisPlugin.mutate,
  updateKlavisPlugin: lambdaClient.klavis.updateKlavisPlugin.mutate,
};

export const klavisService = shouldUseRest('klavis') ? restService : trpcService;
