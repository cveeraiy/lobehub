import { shouldUseRest } from '@/services/_restFlag';

import { socialService as trpcService } from './social';
import { socialService as restService } from './social.rest';

export const socialService = shouldUseRest('social') ? restService : trpcService;
