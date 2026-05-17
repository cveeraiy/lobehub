import { shouldUseRest } from '@/services/_restFlag';

import { agentService as trpcService } from './agent';
import { agentService as restService } from './agent.rest';

export const agentService = shouldUseRest('agent') ? restService : trpcService;

export type { CreateAgentParams, CreateAgentResult } from './agent';
