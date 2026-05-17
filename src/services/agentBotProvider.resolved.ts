import { shouldUseRest } from '@/services/_restFlag';

import { agentBotProviderService as trpcService } from './agentBotProvider';
import { agentBotProviderService as restService } from './agentBotProvider.rest';

export const agentBotProviderService = shouldUseRest('agentBotProvider')
  ? restService
  : trpcService;
