import { shouldUseRest } from '@/services/_restFlag';

import { discoverService as trpcService } from './discover';
import { discoverService as restService } from './discover.rest';

export const discoverService = shouldUseRest('discover') ? restService : trpcService;
