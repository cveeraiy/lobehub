import { shouldUseRest } from '@/services/_restFlag';

import { cloudSandboxService as trpcService } from './cloudSandbox';
import { cloudSandboxService as restService } from './cloudSandbox.rest';

export const cloudSandboxService = shouldUseRest('cloudSandbox') ? restService : trpcService;
