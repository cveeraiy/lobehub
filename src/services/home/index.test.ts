import { beforeEach, describe, expect, it, vi } from 'vitest';

import { homeService } from './index';

const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('HomeService REST', () => {
  it('normalizes sidebar groups and date fields', async () => {
    mockRestGet.mockResolvedValueOnce({
      groups: [
        {
          id: 'group-1',
          items: [
            {
              id: 'agent-2',
              pinned: false,
              title: 'Grouped Agent',
              type: 'agent',
              updatedAt: '2026-05-01T10:00:00.000Z',
            },
          ],
          name: 'Group',
          sort: 0,
        },
      ],
      pinned: [
        {
          id: 'agent-1',
          pinned: true,
          title: 'Pinned Agent',
          type: 'agent',
          updatedAt: '2026-05-02T10:00:00.000Z',
        },
      ],
      ungrouped: [],
    });

    const result = await homeService.getSidebarAgentList();

    expect(mockRestGet).toHaveBeenCalledWith('/home/sidebar-agents');
    expect(result.groups[0].items[0].updatedAt).toBeInstanceOf(Date);
    expect(result.pinned[0].updatedAt).toBeInstanceOf(Date);
  });

  it('keeps backward compatibility with legacy agents group key', async () => {
    mockRestGet.mockResolvedValueOnce({
      groups: [
        {
          agents: [
            {
              id: 'agent-1',
              pinned: false,
              title: 'Legacy Agent',
              type: 'agent',
              updatedAt: '2026-05-01T10:00:00.000Z',
            },
          ],
          id: 'group-1',
          name: 'Group',
          sort: 0,
        },
      ],
      pinned: [],
      ungrouped: [],
    });

    const result = await homeService.getSidebarAgentList();

    expect(result.groups[0].items).toHaveLength(1);
  });

  it('sends snake_case body when moving an agent into a group', async () => {
    mockRestPut.mockResolvedValueOnce(undefined);

    await homeService.updateAgentSessionGroupId('agent-1', 'group-1');

    expect(mockRestPut).toHaveBeenCalledWith('/home/agent-group', {
      body: {
        agent_id: 'agent-1',
        session_group_id: 'group-1',
      },
    });
  });
});
