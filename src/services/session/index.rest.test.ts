import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LobeSessionType } from '@/types/session';

import { sessionService } from './index.rest';

const mockRestDelete = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());
const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: mockRestDelete,
    get: mockRestGet,
    post: mockRestPost,
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SessionService REST', () => {
  it('creates legacy sessions through the REST endpoint', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'session-1' });

    const result = await sessionService.createSession(LobeSessionType.Agent, {
      config: { model: 'gpt-4o', provider: 'openai' } as any,
      group: 'group-1',
      meta: { title: 'REST Session' },
    });

    expect(result).toBe('session-1');
    expect(mockRestPost).toHaveBeenCalledWith('/sessions', {
      body: {
        config: { model: 'gpt-4o', provider: 'openai', title: 'REST Session' },
        session: { groupId: 'group-1' },
        type: LobeSessionType.Agent,
      },
    });
  });

  it('normalizes grouped sessions from the Python REST shape', async () => {
    mockRestGet.mockResolvedValueOnce({
      groups: [
        {
          created_at: '2026-05-01T10:00:00.000Z',
          id: 'group-1',
          name: 'Group',
          sort: 0,
          updated_at: '2026-05-01T11:00:00.000Z',
        },
      ],
      sessions: {
        default: [
          {
            created_at: '2026-05-02T10:00:00.000Z',
            group_id: null,
            id: 'session-1',
            pinned: false,
            type: 'agent',
            updated_at: '2026-05-02T11:00:00.000Z',
          },
        ],
        pinned: [],
      },
    });

    const result = await sessionService.getGroupedSessions();

    expect(result.sessionGroups[0].createdAt).toBeInstanceOf(Date);
    expect(result.sessions[0]).toMatchObject({
      id: 'session-1',
      type: LobeSessionType.Agent,
    });
    expect(result.sessions[0].createdAt).toBeInstanceOf(Date);
  });

  it('updates sessions with snake_case group and timestamp fields', async () => {
    mockRestPut.mockResolvedValueOnce({ ok: true });
    const updatedAt = new Date('2026-05-03T10:00:00.000Z');

    await sessionService.updateSession('session-1', {
      group: 'default',
      pinned: true,
      updatedAt,
    });

    expect(mockRestPut).toHaveBeenCalledWith('/sessions/session-1', {
      body: {
        group_id: null,
        pinned: true,
        updated_at: updatedAt,
      },
    });
  });

  it('uses REST remove-all endpoints for sessions and groups', async () => {
    mockRestPost.mockResolvedValue({ ok: true });

    await sessionService.removeAllSessions();
    await sessionService.removeSessionGroups();

    expect(mockRestPost).toHaveBeenCalledWith('/sessions/remove-all');
    expect(mockRestPost).toHaveBeenCalledWith('/session-groups/remove-all');
  });
});
