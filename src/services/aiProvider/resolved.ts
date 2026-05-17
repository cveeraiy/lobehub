import { shouldUseRest } from '@/services/_restFlag';

import { aiProviderService as trpcService } from './index';
import { aiProviderService as restService } from './index.rest';

export const aiProviderService = shouldUseRest('aiProvider') ? restService : trpcService;
