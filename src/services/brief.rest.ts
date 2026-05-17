/**
 * Brief service — REST API version.
 *
 * Drop-in replacement for `src/services/brief.ts` (TRPC version).
 * Calls the Python backend's `/api/briefs/*` REST endpoints directly.
 *
 * ## How to switch
 * In the store action file (`src/store/brief/slices/list/action.ts`):
 * ```diff
 * -import { briefService } from '@/services/brief';
 * +import { briefService } from '@/services/brief.rest';
 * ```
 * That's it — the interface is identical.
 */
import type { RestApiResponse } from '@/libs/rest';
import { restClient } from '@/libs/rest';

class BriefService {
  delete = async (id: string) => {
    return restClient.delete(`/briefs/${id}`);
  };

  listUnresolved = async (): Promise<RestApiResponse> => {
    return restClient.get<RestApiResponse>('/briefs/unresolved');
  };

  markRead = async (id: string) => {
    return restClient.post(`/briefs/${id}/read`);
  };

  resolve = async (id: string, params?: { action?: string; comment?: string }) => {
    return restClient.post(`/briefs/${id}/resolve`, { body: params });
  };
}

export const briefService = new BriefService();
