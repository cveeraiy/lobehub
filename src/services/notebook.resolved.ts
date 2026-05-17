import { shouldUseRest } from '@/services/_restFlag';

import { notebookService as trpcService } from './notebook';
import { notebookService as restService } from './notebook.rest';

export const notebookService = shouldUseRest('notebook') ? restService : trpcService;
