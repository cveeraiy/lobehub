import { beforeEach, describe, expect, it, vi } from 'vitest';

import { lambdaClient } from '@/libs/trpc/client';

import { fileService } from './index';

vi.mock('@/libs/trpc/client', () => ({
  lambdaClient: {
    file: {
      deleteKnowledgeItemsByQuery: { mutate: vi.fn() },
      getKnowledgeItems: { query: vi.fn() },
      resolveKnowledgeItemIds: { query: vi.fn() },
    },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('FileService TRPC', () => {
  it('omits undefined knowledge item query params while preserving null filters', async () => {
    vi.mocked(lambdaClient.file.getKnowledgeItems.query).mockResolvedValueOnce({
      hasMore: false,
      items: [],
      total: 0,
    } as any);

    await fileService.getKnowledgeItems({
      category: 'all',
      knowledgeBaseId: 'undefined',
      limit: 50,
      offset: 0,
      parentId: null,
      sortType: 'desc',
    });

    expect(lambdaClient.file.getKnowledgeItems.query).toHaveBeenCalledWith({
      category: 'all',
      limit: 50,
      offset: 0,
      parentId: null,
      sortType: 'desc',
    });
  });

  it('compacts selection and delete query params for TRPC calls', async () => {
    vi.mocked(lambdaClient.file.resolveKnowledgeItemIds.query).mockResolvedValueOnce({
      ids: [],
      total: 0,
    } as any);
    vi.mocked(lambdaClient.file.deleteKnowledgeItemsByQuery.mutate).mockResolvedValueOnce({
      count: 0,
    } as any);

    const params = {
      category: 'all',
      knowledgeBaseId: undefined,
      limit: 50,
      offset: 0,
    };

    await fileService.resolveKnowledgeItemIds(params);
    await fileService.deleteKnowledgeItemsByQuery(params);

    expect(lambdaClient.file.resolveKnowledgeItemIds.query).toHaveBeenCalledWith({
      category: 'all',
      limit: 50,
      offset: 0,
    });
    expect(lambdaClient.file.deleteKnowledgeItemsByQuery.mutate).toHaveBeenCalledWith({
      category: 'all',
      limit: 50,
      offset: 0,
    });
  });
});
