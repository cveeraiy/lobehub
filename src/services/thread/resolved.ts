import { shouldUseRest } from '@/services/_restFlag';

import { threadService as trpcService } from './index';
import { threadService as restService } from './index.rest';

export const threadService = shouldUseRest('thread') ? restService : trpcService;
