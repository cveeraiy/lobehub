import { shouldUseRest } from '@/services/_restFlag';

import { agentCronJobService as trpcService } from './agentCronJob';
import { agentCronJobService as restService } from './agentCronJob.rest';

export const agentCronJobService = shouldUseRest('agentCronJob') ? restService : trpcService;
