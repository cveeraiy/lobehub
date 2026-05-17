/**
 * Resolved brief service — picks TRPC or REST based on the feature flag.
 *
 * ## How to adopt (when ready)
 * In any store that imports `briefService`:
 * ```diff
 * -import { briefService } from '@/services/brief';
 * +import { briefService } from '@/services/brief.resolved';
 * ```
 */
import { shouldUseRest } from '@/services/_restFlag';

import { briefService as trpcService } from './brief';
import { briefService as restService } from './brief.rest';

export const briefService = shouldUseRest('brief') ? restService : trpcService;
