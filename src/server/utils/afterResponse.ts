const pendingTasks = new Set<Promise<void>>();

/**
 * Framework-agnostic replacement for Next.js `after()`.
 *
 * Schedules a fire-and-forget async task that runs after the current
 * response is sent. Tasks are tracked so the graceful shutdown handler
 * can wait for them before exiting.
 *
 * Usage is identical to `after()` from `next/server`:
 *
 * ```ts
 * import { afterResponse } from '@/server/utils/afterResponse';
 * afterResponse(async () => { ... });
 * ```
 */
export function afterResponse(fn: () => Promise<void> | void): void {
  const defer =
    typeof setImmediate === 'function' ? setImmediate : (cb: () => void) => setTimeout(cb, 0);

  defer(() => {
    try {
      const result = fn();
      if (result && typeof result.then === 'function') {
        const tracked = (result as Promise<void>)
          .catch((err: unknown) => {
            console.error('[afterResponse] Unhandled error in deferred task:', err);
          })
          .finally(() => {
            pendingTasks.delete(tracked);
          });
        pendingTasks.add(tracked);
      }
    } catch (err) {
      console.error('[afterResponse] Synchronous error in deferred task:', err);
    }
  });
}
