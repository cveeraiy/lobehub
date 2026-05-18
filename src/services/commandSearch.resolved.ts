import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import { commandSearchService as restService } from './commandSearch.rest';

const trpcService = {
  query: lambdaClient.search.query.query,
};

export const commandSearchService = shouldUseRest('search') ? restService : trpcService;
