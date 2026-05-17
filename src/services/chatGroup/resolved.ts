import { shouldUseRest } from '@/services/_restFlag';

import { chatGroupService as trpcService } from './index';
import { chatGroupService as restService } from './index.rest';

export const chatGroupService = shouldUseRest('chatGroup') ? restService : trpcService;
