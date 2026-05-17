/**
 * Resolved Agent Runtime service — picks TRPC or REST based on the feature flag.
 *
 * ## How to adopt (when ready)
 * In any store that imports `agentRuntimeService`:
 * ```diff
 * -import { agentRuntimeService } from '@/services/agentRuntime';
 * +import { agentRuntimeService } from '@/services/agentRuntime/resolved';
 * ```
 */
import { shouldUseRest } from '@/services/_restFlag';

import { agentRuntimeService as trpcService } from './index';
import { agentRuntimeService as restService } from './index.rest';

export const agentRuntimeService = shouldUseRest('agentRuntime') ? restService : trpcService;

export { agentRuntimeClient } from './client';
export * from './type';
