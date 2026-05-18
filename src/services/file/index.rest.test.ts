import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { fileService } from './index.rest';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('FileService REST', () => {
  it('maps knowledge item query params and response shape', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      has_more: false,
      items: [
        {
          created_at: '2026-01-01T00:00:00.000Z',
          file_type: 'text/plain',
          id: 'file-1',
          name: 'File 1',
          parent_id: null,
          size: 12,
          source_type: 'file',
          updated_at: '2026-01-02T00:00:00.000Z',
          url: '/file.txt',
        },
      ],
      total: 1,
    });

    const result = await fileService.getKnowledgeItems({
      knowledgeBaseId: 'kb-1',
      limit: 50,
      offset: 0,
      sortType: 'desc',
    });

    expect(restClient.get).toHaveBeenCalledWith('/files/knowledge-items', {
      params: {
        knowledge_base_id: 'kb-1',
        limit: 50,
        offset: 0,
        sort_type: 'desc',
      },
    });
    expect(result).toMatchObject({
      hasMore: false,
      items: [
        {
          fileType: 'text/plain',
          id: 'file-1',
          name: 'File 1',
          parentId: null,
          sourceType: 'file',
          url: '/file.txt',
        },
      ],
      total: 1,
    });
  });

  it('omits null and frontend-only knowledge item query params', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      has_more: false,
      items: [],
      total: 0,
    });

    await fileService.getKnowledgeItems({
      category: 'all',
      limit: 50,
      offset: 0,
      parentId: null,
      showFilesInKnowledgeBase: false,
      sortType: 'desc',
      sorter: 'createdAt',
    });

    expect(restClient.get).toHaveBeenCalledWith('/files/knowledge-items', {
      params: {
        category: 'all',
        limit: 50,
        offset: 0,
        sort_type: 'desc',
        sorter: 'createdAt',
      },
    });
  });
});
