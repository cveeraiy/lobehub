import { shouldUseRest } from '@/services/_restFlag';

import { importService as trpcService } from './index';
import { importService as restService } from './index.rest';

export const importService = shouldUseRest('import') ? restService : trpcService;
