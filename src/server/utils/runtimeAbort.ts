const DEFAULT_ABORT_MESSAGE = 'Agent execution aborted';

export function createAbortError(message = DEFAULT_ABORT_MESSAGE): Error {
  const error = new Error(message);
  error.name = 'AbortError';
  return error;
}

export function isAbortError(error: unknown): error is Error {
  return error instanceof Error && error.name === 'AbortError';
}
