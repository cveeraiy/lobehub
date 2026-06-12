import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import { notebookService } from '@/services/notebook';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('NotebookService', () => {
  it('creates documents through the REST notebook endpoint', async () => {
    vi.mocked(restClient.post).mockResolvedValue({
      content: 'body',
      created_at: '2026-05-20T10:00:00.000Z',
      file_type: 'markdown',
      id: 'doc-1',
      title: 'Doc',
      total_char_count: 4,
      total_line_count: 1,
      updated_at: '2026-05-20T10:00:00.000Z',
    });

    const result = await notebookService.createDocument({
      content: 'body',
      description: 'desc',
      title: 'Doc',
      topicId: 'topic-1',
      type: 'markdown',
    });

    expect(restClient.post).toHaveBeenCalledWith('/notebook/documents', {
      body: {
        content: 'body',
        description: 'desc',
        metadata: undefined,
        source: undefined,
        source_type: undefined,
        title: 'Doc',
        topic_id: 'topic-1',
        type: 'markdown',
      },
    });
    expect(result.id).toBe('doc-1');
    expect(result.createdAt).toBeInstanceOf(Date);
  });

  it('preserves append behavior when updating document content', async () => {
    vi.mocked(restClient.get).mockResolvedValue({
      content: 'existing',
      id: 'doc-1',
    });
    vi.mocked(restClient.put).mockResolvedValue({
      content: 'existing\n\nnext',
      id: 'doc-1',
    });

    await notebookService.updateDocument({
      append: true,
      content: 'next',
      id: 'doc-1',
    });

    expect(restClient.get).toHaveBeenCalledWith('/notebook/documents/doc-1');
    expect(restClient.put).toHaveBeenCalledWith('/notebook/documents/doc-1', {
      body: { content: 'existing\n\nnext' },
    });
  });

  it('normalizes list responses from REST arrays', async () => {
    vi.mocked(restClient.get).mockResolvedValue([
      {
        content: 'body',
        id: 'doc-1',
        title: 'Doc',
      },
    ]);

    const result = await notebookService.listDocuments({ topicId: 'topic-1' });

    expect(restClient.get).toHaveBeenCalledWith('/notebook/documents', {
      params: { topic_id: 'topic-1', type: undefined },
    });
    expect(result).toMatchObject({
      data: [{ id: 'doc-1', title: 'Doc' }],
      total: 1,
    });
  });
});
