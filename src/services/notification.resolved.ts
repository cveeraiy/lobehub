import { shouldUseRest } from '@/services/_restFlag';

import { notificationService as trpcService } from './notification';
import { notificationService as restService } from './notification.rest';

export const notificationService = shouldUseRest('notification') ? restService : trpcService;
