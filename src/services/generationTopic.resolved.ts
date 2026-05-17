import { shouldUseRest } from '@/services/_restFlag';

import { generationTopicService as trpcService } from './generationTopic';
import { generationTopicService as restService } from './generationTopic.rest';

export const generationTopicService = shouldUseRest('generationTopic') ? restService : trpcService;
