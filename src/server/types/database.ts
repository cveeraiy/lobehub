/**
 * Transitional database handle types for retired TypeScript backend code.
 *
 * Python owns database access now; remaining TS server modules are being deleted or
 * replaced by REST calls. Keep these types local so type-only imports no longer
 * force non-database packages to depend on the retired database workspace package.
 */
export type LobeChatDatabase = any;

export type Transaction = any;
