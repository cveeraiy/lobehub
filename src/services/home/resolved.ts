import { shouldUseRest } from '@/services/_restFlag';

import { homeService as trpcService } from './index';
import { homeService as restService } from './index.rest';

export const homeService = shouldUseRest('home') ? restService : trpcService;
