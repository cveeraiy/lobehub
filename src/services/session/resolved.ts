import { shouldUseRest } from '@/services/_restFlag';

import { sessionService as trpcService } from './index';
import { sessionService as restService } from './index.rest';

export const sessionService = shouldUseRest('session') ? restService : trpcService;
