import { shouldUseRest } from '@/services/_restFlag';

import { knowledgeBaseService as trpcService } from './knowledgeBase';
import { knowledgeBaseService as restService } from './knowledgeBase.rest';

export const knowledgeBaseService = shouldUseRest('knowledgeBase') ? restService : trpcService;
