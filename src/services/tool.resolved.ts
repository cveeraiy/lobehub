import { shouldUseRest } from '@/services/_restFlag';

import { toolService as trpcService } from './tool';
import { toolService as restService } from './tool.rest';

export const toolService = shouldUseRest('market') ? restService : trpcService;
