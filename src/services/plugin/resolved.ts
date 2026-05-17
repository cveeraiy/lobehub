import { shouldUseRest } from '@/services/_restFlag';

import { pluginService as trpcService } from './index';
import { pluginService as restService } from './index.rest';

export const pluginService = shouldUseRest('plugin') ? restService : trpcService;
