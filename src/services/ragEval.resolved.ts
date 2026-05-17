import { shouldUseRest } from '@/services/_restFlag';

import { ragEvalService as trpcService } from './ragEval';
import { ragEvalService as restService } from './ragEval.rest';

export const ragEvalService = shouldUseRest('ragEval') ? restService : trpcService;
