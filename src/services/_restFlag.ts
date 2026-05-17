/**
 * Feature flag controlling whether services use REST (Python backend)
 * or TRPC (TS backend).
 *
 * ## Usage
 * ```ts
 * import { useRestApi, REST_DOMAINS } from '@/services/_restFlag';
 *
 * // Global check
 * if (useRestApi()) { ... }
 *
 * // Per-domain check
 * if (REST_DOMAINS.has('user')) { ... }
 * ```
 *
 * ## How to enable
 * - Set `NEXT_PUBLIC_USE_REST_API=1` in your `.env` to enable for ALL domains.
 * - Set `NEXT_PUBLIC_REST_DOMAINS=user,brief` to enable only for specific domains.
 * - Both can be combined: global flag enables everything, domain list is additive.
 *
 * ## Default: off (all traffic goes through TRPC)
 */

// Vite/Rolldown `define` replaces `process.env.NEXT_PUBLIC_*` with literals.
// We must reference the full dotted expression on a single line so the
// replacement can fire. Do NOT destructure or alias `process.env` first.
const GLOBAL_FLAG: boolean = process.env.NEXT_PUBLIC_USE_REST_API === '1';
const DOMAIN_LIST: string = process.env.NEXT_PUBLIC_REST_DOMAINS ?? '';

/**
 * Set of domain names that should use REST.
 * Empty set = none (unless global flag is on).
 *
 * Valid domain names match service file stems:
 *   'user' | 'brief' | 'session' | 'topic' | 'message' | 'agent' | ...
 */
export const REST_DOMAINS: ReadonlySet<string> = new Set(
  DOMAIN_LIST.split(',')
    .map((s) => s.trim())
    .filter(Boolean),
);

/**
 * Returns true if the given domain (or all domains when global flag is on)
 * should use the REST service instead of TRPC.
 */
export const shouldUseRest = (domain: string): boolean => {
  if (GLOBAL_FLAG) return true;
  return REST_DOMAINS.has(domain);
};
