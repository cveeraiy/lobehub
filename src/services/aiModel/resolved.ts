import { shouldUseRest } from '@/services/_restFlag';

import { aiModelService as trpcService } from './index';
import { aiModelService as restService } from './index.rest';

export const aiModelService = shouldUseRest('aiModel') ? restService : trpcService;
