/**
 * Registry of in-flight afterResponse tasks.
 * Used by the graceful shutdown handler to wait for pending tasks before exiting.
 */
export const pendingTasks = new Set<Promise<void>>();
