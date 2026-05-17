import { shouldUseRest } from '@/services/_restFlag';

import { marketAuthService as trpcService } from './marketAuth';
import { marketAuthService as restService } from './marketAuth.rest';

export const marketAuthService = shouldUseRest('user') ? restService : trpcService;
