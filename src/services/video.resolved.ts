import { shouldUseRest } from '@/services/_restFlag';

import { videoService as trpcService } from './video';
import { videoService as restService } from './video.rest';

export const videoService = shouldUseRest('video') ? restService : trpcService;
