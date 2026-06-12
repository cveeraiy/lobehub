/**
 * Next.js navigation compat layer.
 *
 * Thin wrapper around `@/libs/router/navigation` that provides a
 * Next.js-compatible API surface (e.g. `useSearchParams` returns
 * `URLSearchParams` directly instead of a `[params, setter]` tuple).
 *
 * Auth pages and legacy code import from here; new code should use
 * `@/libs/router/navigation` directly.
 */

import { useSearchParams as useReactRouterSearchParams } from 'react-router-dom';

export { useParams, usePathname, useRouter } from '@/libs/router/navigation';

/**
 * Next.js-compat `useSearchParams`.
 * Returns `URLSearchParams` directly (Next.js API), unlike react-router-dom
 * which returns a `[searchParams, setSearchParams]` tuple.
 */
export function useSearchParams(): URLSearchParams {
  const [searchParams] = useReactRouterSearchParams();
  return searchParams;
}

// ---------------------------------------------------------------------------
// Types kept for backward compat
// ---------------------------------------------------------------------------
export type RedirectType = 'push' | 'replace';
export type ReadonlyURLSearchParams = URLSearchParams;
