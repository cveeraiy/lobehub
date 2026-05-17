import { shouldUseRest } from '@/services/_restFlag';

import {
  memoryCRUDService as trpcCRUD,
  memoryExtractionService as trpcExtraction,
  userMemoryService as trpcService,
} from './index';
import {
  memoryCRUDService as restCRUD,
  memoryExtractionService as restExtraction,
  userMemoryService as restService,
} from './index.rest';

export const userMemoryService = shouldUseRest('userMemory') ? restService : trpcService;
export const memoryCRUDService = shouldUseRest('userMemory') ? restCRUD : trpcCRUD;
export const memoryExtractionService = shouldUseRest('userMemory')
  ? restExtraction
  : trpcExtraction;
