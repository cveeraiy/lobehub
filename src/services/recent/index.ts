import { restClient } from '@/libs/rest';
import type { RecentItem } from '@/types/recent';

type RawRecentItem = Omit<RecentItem, 'updatedAt'> & {
  updatedAt?: string | null;
};

const toRecentItem = (item: RawRecentItem): RecentItem => ({
  ...item,
  updatedAt: item.updatedAt ? new Date(item.updatedAt) : new Date(0),
});

class RecentService {
  getAll = async (limit?: number): Promise<RecentItem[]> => {
    const response = await restClient.get<RawRecentItem[]>('/recent', {
      params: limit ? { limit } : undefined,
    });
    return response.map(toRecentItem);
  };
}

export const recentService = new RecentService();
