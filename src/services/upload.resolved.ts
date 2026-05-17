import { shouldUseRest } from '@/services/_restFlag';

import { uploadService as trpcService } from './upload';
import { uploadService as restService } from './upload.rest';

export const uploadService = shouldUseRest('upload') ? restService : trpcService;
