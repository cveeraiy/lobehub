/**
 * Resolved user service — picks TRPC or REST based on the feature flag.
 *
 * ## How to adopt (when ready)
 * In any store that imports `userService`:
 * ```diff
 * -import { userService } from '@/services/user';
 * +import { userService } from '@/services/user/resolved';
 * ```
 *
 * Then control the backend via env var:
 *   NEXT_PUBLIC_REST_DOMAINS=user   → REST
 *   (unset)                         → TRPC (default)
 */
import { shouldUseRest } from '@/services/_restFlag';

import { userService as trpcService } from './index';
import { userService as restService } from './index.rest';

export const userService = shouldUseRest('user') ? restService : trpcService;

export type { UserService } from './index';
