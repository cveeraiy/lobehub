import { shouldUseRest } from '@/services/_restFlag';

import { imageService as trpcService } from './image';
import { imageService as restService } from './image.rest';

export const imageService = shouldUseRest('image') ? restService : trpcService;
