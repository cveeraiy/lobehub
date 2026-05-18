import { shouldUseRest } from '@/services/_restFlag';

import { marketApiService as trpcService } from './marketApi';
import { marketApiService as restService } from './marketApi.rest';

export const marketApiService = (
  shouldUseRest('market') ? restService : trpcService
) as typeof restService;
