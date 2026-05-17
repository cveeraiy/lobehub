import { shouldUseRest } from '@/services/_restFlag';

import { taskService as trpcService } from './task';
import { taskService as restService } from './task.rest';

export const taskService = shouldUseRest('task') ? restService : trpcService;
