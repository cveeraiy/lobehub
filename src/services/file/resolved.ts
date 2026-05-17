import { shouldUseRest } from '@/services/_restFlag';

import { fileService as trpcService } from './index';
import { fileService as restService } from './index.rest';

export const fileService = shouldUseRest('file') ? restService : trpcService;
