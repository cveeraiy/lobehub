/**
 * Standard REST API response envelope returned by Python FastAPI routers.
 *
 * All Python routers wrap responses in `{ success: true, data: T }` for
 * success and `{ success: false, detail: string }` for errors.
 */
export interface RestApiResponse<T = unknown> {
  data?: T;
  success: boolean;
  total?: number;
}

/**
 * Error shape from the Python backend (FastAPI HTTPException / validation error).
 */
export interface RestApiError {
  code?: string;
  detail?: string;
  message?: string;
}
