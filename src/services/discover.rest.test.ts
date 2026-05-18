import { beforeEach, describe, expect, it, vi } from 'vitest';

import { discoverService } from './discover.rest';

const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
    post: mockRestPost,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = 'mp_token_status=active';
});

describe('DiscoverService REST', () => {
  it('normalizes MCP list pagination from snake_case fields', async () => {
    mockRestGet.mockResolvedValueOnce({
      current_page: 2,
      items: [{ identifier: 'mcp-1', name: 'MCP One' }],
      page_size: 20,
      total_count: 21,
      total_pages: 2,
    });

    const result = await discoverService.getMCPPluginList({ page: 2, pageSize: 20, q: 'mcp' });

    expect(mockRestGet).toHaveBeenCalledWith('/discover/mcp/list', {
      params: expect.objectContaining({ page: 2, pageSize: 20, q: 'mcp' }),
    });
    expect(result).toMatchObject({
      currentPage: 2,
      pageSize: 20,
      totalCount: 21,
      totalPages: 2,
    });
    expect(result.items).toEqual([{ identifier: 'mcp-1', name: 'MCP One' }]);
  });

  it('normalizes skill list responses with data arrays', async () => {
    mockRestGet.mockResolvedValueOnce({
      data: [{ identifier: 'skill-1', name: 'Skill One' }],
      total: 1,
    });

    const result = await discoverService.getSkillList({ page: 1, pageSize: 20 });

    expect(mockRestGet).toHaveBeenCalledWith('/discover/skill/list', {
      params: expect.objectContaining({ page: 1, pageSize: 20 }),
    });
    expect(result).toMatchObject({
      currentPage: 1,
      pageSize: 20,
      totalCount: 1,
      totalPages: 1,
    });
    expect(result.items).toEqual([{ identifier: 'skill-1', name: 'Skill One' }]);
  });
});
