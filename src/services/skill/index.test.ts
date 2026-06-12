import { beforeEach, describe, expect, it, vi } from 'vitest';

import { agentSkillService } from './index';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AgentSkillService REST', () => {
  it('normalizes list responses from item-based Python pagination', async () => {
    mockRestGet.mockResolvedValueOnce({
      items: [
        {
          created_at: '2026-05-01T10:00:00.000Z',
          description: 'Review code',
          id: 'skill-1',
          identifier: 'code-review',
          manifest: { description: 'Review code', name: 'Code Review' },
          name: 'Code Review',
          source: 'market',
          updated_at: '2026-05-01T11:00:00.000Z',
          zip_file_hash: 'zip-hash',
        },
      ],
      total_count: 1,
    });

    const result = await agentSkillService.list();

    expect(mockRestGet).toHaveBeenCalledWith('/skills', { params: undefined });
    expect(result.total).toBe(1);
    expect(result.data[0]).toMatchObject({
      id: 'skill-1',
      identifier: 'code-review',
      source: 'market',
      zipFileHash: 'zip-hash',
    });
    expect(result.data[0].createdAt).toBeInstanceOf(Date);
    expect(result.data[0].updatedAt).toBeInstanceOf(Date);
  });

  it('normalizes array list responses', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        created_at: '2026-05-01T10:00:00.000Z',
        id: 'skill-1',
        identifier: 'code-review',
        name: 'Code Review',
        updated_at: '2026-05-01T11:00:00.000Z',
      },
    ]);

    const result = await agentSkillService.search('code');

    expect(mockRestGet).toHaveBeenCalledWith('/skills/search', { params: { query: 'code' } });
    expect(result.total).toBe(1);
    expect(result.data[0]).toMatchObject({
      id: 'skill-1',
      identifier: 'code-review',
      name: 'Code Review',
      source: 'user',
    });
  });
});
