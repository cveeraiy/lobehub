import { beforeEach, describe, expect, it, vi } from 'vitest';

import { recentService } from './index.rest';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('RecentService REST', () => {
  it('passes the limit and normalizes updatedAt to Date', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        icon: 'topic',
        id: 'topic-1',
        routePath: '/agent/agent-1/topic-1',
        title: 'Recent Topic',
        type: 'topic',
        updatedAt: '2026-05-01T10:00:00.000Z',
      },
    ]);

    const result = await recentService.getAll(12);

    expect(mockRestGet).toHaveBeenCalledWith('/recent', { params: { limit: 12 } });
    expect(result[0].updatedAt).toBeInstanceOf(Date);
  });

  it('omits query params when limit is not provided', async () => {
    mockRestGet.mockResolvedValueOnce([]);

    await recentService.getAll();

    expect(mockRestGet).toHaveBeenCalledWith('/recent', { params: undefined });
  });
});
