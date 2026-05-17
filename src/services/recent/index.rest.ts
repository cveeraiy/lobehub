import { restClient } from '@/libs/rest';

class RecentService {
  getAll = (limit?: number): Promise<any[]> => {
    return restClient.get('/recent', { params: limit ? { limit } : undefined });
  };
}

export const recentService = new RecentService();
