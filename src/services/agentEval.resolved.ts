import { shouldUseRest } from '@/services/_restFlag';

import { agentEvalService as trpcService } from './agentEval';
import { agentEvalService as restService } from './agentEval.rest';

export const agentEvalService = shouldUseRest('agentEval') ? restService : trpcService;
