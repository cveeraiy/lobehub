import { shouldUseRest } from '@/services/_restFlag';

import { exportService as trpcService } from './index';
import { exportService as restService } from './index.rest';

export const exportService = shouldUseRest('export') ? restService : trpcService;
