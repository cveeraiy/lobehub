import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { socialService } from './social';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SocialService REST', () => {
  it('adds favorites by identifier through the REST proxy', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce(undefined);

    await socialService.addFavorite('plugin', 'plugin-id');

    expect(restClient.post).toHaveBeenCalledWith('/social/favorite', {
      body: { identifier: 'plugin-id', targetType: 'plugin' },
    });
  });

  it('checks favorite status with the existing targetIdOrIdentifier contract', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({ isFavorited: true });

    const result = await socialService.checkFavoriteStatus('agent', 42);

    expect(restClient.get).toHaveBeenCalledWith('/social/favorite-status', {
      params: { targetIdOrIdentifier: 42, targetType: 'agent' },
    });
    expect(result).toEqual({ isFavorited: true });
  });

  it('maps page pagination to limit and offset', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      currentPage: 3,
      items: [],
      pageSize: 20,
      totalCount: 0,
      totalPages: 0,
    });

    await socialService.getFollowers(7, { page: 3, pageSize: 20 });

    expect(restClient.get).toHaveBeenCalledWith('/social/followers', {
      params: {
        limit: 20,
        offset: 40,
        userId: 7,
      },
    });
  });
});
