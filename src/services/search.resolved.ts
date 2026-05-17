import { shouldUseRest } from '@/services/_restFlag';

import { searchService as trpcService } from './search';
import { searchService as restService } from './search.rest';

export const searchService = shouldUseRest('search') ? restService : trpcService;
