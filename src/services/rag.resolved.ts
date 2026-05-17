import { shouldUseRest } from '@/services/_restFlag';

import { ragService as trpcService } from './rag';
import { ragService as restService } from './rag.rest';

export const ragService = shouldUseRest('rag') ? restService : trpcService;
