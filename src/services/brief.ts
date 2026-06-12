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
