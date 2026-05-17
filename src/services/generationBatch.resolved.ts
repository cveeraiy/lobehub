import { shouldUseRest } from '@/services/_restFlag';

import { generationBatchService as trpcService } from './generationBatch';
import { generationBatchService as restService } from './generationBatch.rest';

export const generationBatchService = shouldUseRest('generationBatch') ? restService : trpcService;
