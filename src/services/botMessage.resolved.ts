import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { botMessageService as restService } from './botMessage.rest';

const trpcService = {
  call: async (apiName: string, params: Record<string, unknown>, method: 'mutate' | 'query') => {
    const router = lambdaClient.botMessage as unknown as Record<
      string,
      {
        mutate?: (input: Record<string, unknown>) => Promise<unknown>;
        query?: (input: Record<string, unknown>) => Promise<unknown>;
      }
    >;
    const procedure = router[apiName];
    if (!procedure) throw new Error(`Unknown message API: ${apiName}`);

    if (method === 'query') {
      if (!procedure.query) throw new Error(`Message API is not queryable: ${apiName}`);
      return procedure.query(params);
    }

    if (!procedure.mutate) throw new Error(`Message API is not mutable: ${apiName}`);
    return procedure.mutate(params);
  },
};

export const botMessageService = shouldUseRest('botMessage') ? restService : trpcService;
