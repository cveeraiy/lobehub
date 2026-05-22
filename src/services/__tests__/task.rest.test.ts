import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import { taskService } from '@/services/task';

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

describe('Task REST service', () => {
  it('normalizes REST task status aliases in task detail payloads', async () => {
    vi.mocked(restClient.get).mockResolvedValue({
      data: {
        activities: [{ id: 'topic-1', status: 'pending', type: 'topic' }],
        identifier: 'T-1',
        status: 'in_progress',
        subtasks: [{ identifier: 'T-2', status: 'done' }],
      },
      success: true,
    });

    const result = await taskService.getDetail('T-1');

    expect(result).toEqual({
      data: {
        activities: [{ id: 'topic-1', status: 'pending', type: 'topic' }],
        identifier: 'T-1',
        status: 'running',
        subtasks: [{ identifier: 'T-2', status: 'completed' }],
      },
      success: true,
    });
  });

  it('normalizes REST task status aliases in grouped task lists', async () => {
    vi.mocked(restClient.post).mockResolvedValue({
      data: {
        backlog: {
          tasks: [{ identifier: 'T-1', status: 'pending' }],
          total: 1,
        },
        done: {
          tasks: [{ identifier: 'T-2', status: 'done' }],
          total: 1,
        },
      },
      success: true,
    });

    const result = await taskService.groupList({
      groups: [
        { key: 'backlog', statuses: ['backlog'] },
        { key: 'done', statuses: ['completed'] },
      ],
    });

    expect(restClient.post).toHaveBeenCalledWith('/tasks/group-list', {
      body: {
        groups: [
          { key: 'backlog', statuses: ['backlog', 'pending'] },
          { key: 'done', statuses: ['completed', 'done'] },
        ],
      },
    });
    expect(result).toEqual({
      data: [
        {
          hasMore: false,
          key: 'backlog',
          limit: 50,
          offset: 0,
          tasks: [{ identifier: 'T-1', status: 'backlog' }],
          total: 1,
        },
        {
          hasMore: false,
          key: 'done',
          limit: 50,
          offset: 0,
          tasks: [{ identifier: 'T-2', status: 'completed' }],
          total: 1,
        },
      ],
      success: true,
    });
  });
});
