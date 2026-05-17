/**
 * Resolved AI Agent service — picks TRPC or REST based on the feature flag.
 *
 * ## How to adopt (when ready)
 * In any store that imports `aiAgentService`:
 * ```diff
 * -import { aiAgentService } from '@/services/aiAgent';
 * +import { aiAgentService } from '@/services/aiAgent.resolved';
 * ```
 */
import { shouldUseRest } from '@/services/_restFlag';

import { aiAgentService as trpcService } from './aiAgent';
import { aiAgentService as restService } from './aiAgent.rest';

export const aiAgentService = shouldUseRest('aiAgent') ? restService : trpcService;

export type { ResumeApprovalParam } from './aiAgent';
