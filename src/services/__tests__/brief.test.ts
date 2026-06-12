import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { briefService } from '../brief';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('BriefService', () => {
  describe('listUnresolved', () => {
    it('should call unresolved briefs endpoint', async () => {
      const mockData = { data: [{ id: 'brief-1', title: 'Test' }], success: true };
      vi.mocked(restClient.get).mockResolvedValueOnce(mockData);

      const result = await briefService.listUnresolved();

      expect(restClient.get).toHaveBeenCalledWith('/briefs/unresolved');
      expect(result).toEqual(mockData);
    });
  });

  describe('resolve', () => {
    it('should call resolve endpoint with params', async () => {
      vi.mocked(restClient.post).mockResolvedValueOnce({ data: {}, success: true });

      await briefService.resolve('brief-1', { action: 'approve', comment: 'looks good' });

      expect(restClient.post).toHaveBeenCalledWith('/briefs/brief-1/resolve', {
        body: {
          action: 'approve',
          comment: 'looks good',
        },
      });
    });

    it('should call resolve endpoint with undefined body when no params', async () => {
      vi.mocked(restClient.post).mockResolvedValueOnce({ data: {}, success: true });

      await briefService.resolve('brief-1');

      expect(restClient.post).toHaveBeenCalledWith('/briefs/brief-1/resolve', {
        body: undefined,
      });
    });
  });

  describe('markRead', () => {
    it('should call read endpoint', async () => {
      vi.mocked(restClient.post).mockResolvedValueOnce({ data: {}, success: true });

      await briefService.markRead('brief-1');

      expect(restClient.post).toHaveBeenCalledWith('/briefs/brief-1/read');
    });
  });
});
