import { shouldUseRest } from '@/services/_restFlag';

import { followUpActionService as trpcService } from './followUpAction';
import { followUpActionService as restService } from './followUpAction.rest';

export const followUpActionService = shouldUseRest('followUpAction') ? restService : trpcService;
