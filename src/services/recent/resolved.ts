import { shouldUseRest } from '@/services/_restFlag';

import { recentService as trpcService } from './index';
import { recentService as restService } from './index.rest';

export const recentService = shouldUseRest('recent') ? restService : trpcService;
