import { shouldUseRest } from '@/services/_restFlag';

import { agentSkillService as trpcService } from './index';
import { agentSkillService as restService } from './index.rest';

export const agentSkillService = shouldUseRest('skill') ? restService : trpcService;
