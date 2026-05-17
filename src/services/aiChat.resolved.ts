/**
 * Resolved AI Chat service — picks TRPC or REST based on the feature flag.
 *
 * ## How to adopt (when ready)
 * In any store that imports `aiChatService`:
 * ```diff
 * -import { aiChatService } from '@/services/aiChat';
 * +import { aiChatService } from '@/services/aiChat.resolved';
 * ```
 */
import { shouldUseRest } from '@/services/_restFlag';

import { aiChatService as trpcService } from './aiChat';
import { aiChatService as restService } from './aiChat.rest';

export const aiChatService = shouldUseRest('aiChat') ? restService : trpcService;
