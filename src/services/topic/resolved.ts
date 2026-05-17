import { shouldUseRest } from '@/services/_restFlag';

import { topicService as trpcService } from './index';
import { topicService as restService } from './index.rest';

export const topicService = shouldUseRest('topic') ? restService : trpcService;
