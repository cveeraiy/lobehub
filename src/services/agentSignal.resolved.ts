import { shouldUseRest } from '@/services/_restFlag';

import { agentSignalService as trpcService } from './agentSignal';
import { agentSignalService as restService } from './agentSignal.rest';

export const agentSignalService = shouldUseRest('agentSignal') ? restService : trpcService;
