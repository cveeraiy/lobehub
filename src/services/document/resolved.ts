import { shouldUseRest } from '@/services/_restFlag';

import { documentService as trpcService } from './index';
import { documentService as restService } from './index.rest';

export const documentService = shouldUseRest('document') ? restService : trpcService;
