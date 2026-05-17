import { shouldUseRest } from '@/services/_restFlag';

import { globalService as trpcService } from './global';
import { globalService as restService } from './global.rest';

export const globalService = shouldUseRest('global') ? restService : trpcService;
