import { shouldUseRest } from '@/services/_restFlag';

import { usageService as trpcService } from './usage';
import { usageService as restService } from './usage.rest';

export const usageService = shouldUseRest('usage') ? restService : trpcService;
