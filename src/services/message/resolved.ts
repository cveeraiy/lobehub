import { shouldUseRest } from '@/services/_restFlag';

import { messageService as trpcService } from './index';
import { messageService as restService } from './index.rest';

export const messageService = shouldUseRest('message') ? restService : trpcService;
