import { restClient } from '@/libs/rest';

class UsageService {
  findByMonth = async (mo?: string) => {
    return restClient.get('/usage/by-month', { params: mo ? { month: mo } : undefined });
  };

  findAndGroupByDay = async (mo?: string) => {
    return restClient.get('/usage/by-day', { params: mo ? { month: mo } : undefined });
  };
}

export const usageService = new UsageService();
