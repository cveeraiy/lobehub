/**
 * Prepare Request object for tRPC fetchRequestHandler
 *
 * Clones the Request to create an independent body stream so that tRPC
 * can safely read the body even if the original request's body was
 * consumed by framework internals.
 *
 * @param req - The original Request object
 * @returns A cloned Request object with an independent body stream
 */
export function prepareRequestForTRPC(req: Request): Request {
  return req.clone();
}
