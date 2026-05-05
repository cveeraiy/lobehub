import { AsyncLocalStorage } from 'node:async_hooks';

/**
 * AsyncLocalStorage to propagate the current Request through the OIDC provider
 * callback chain so that deeply nested code (e.g. the adapter's upsert) can
 * access the original request without it being passed as a parameter.
 */
export const oidcRequestStorage = new AsyncLocalStorage<Request>();
