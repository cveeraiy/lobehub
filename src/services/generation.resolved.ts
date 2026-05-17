import { shouldUseRest } from '@/services/_restFlag';

import { generationService as trpcService } from './generation';
import { generationService as restService } from './generation.rest';

export const generationService = shouldUseRest('generation') ? restService : trpcService;
