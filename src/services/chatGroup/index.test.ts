import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { chatGroupService } from './index';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('chatGroupService REST', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates groups through the chat-groups REST endpoint and normalizes snake_case fields', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({
      group: {
        background_color: 'red',
        client_id: 'client-1',
        created_at: '2026-05-01T10:00:00.000Z',
        group_id: 'folder-1',
        id: 'group-1',
        title: 'Test Group',
        updated_at: '2026-05-01T11:00:00.000Z',
      },
      supervisor_agent_id: 'agent-supervisor',
    });

    const result = await chatGroupService.createGroup({
      backgroundColor: 'red',
      clientId: 'client-1',
      groupId: 'folder-1',
      title: 'Test Group',
    });

    expect(restClient.post).toHaveBeenCalledWith('/chat-groups', {
      body: expect.objectContaining({
        background_color: 'red',
        client_id: 'client-1',
        group_id: 'folder-1',
        title: 'Test Group',
      }),
    });
    expect(result).toMatchObject({
      group: {
        backgroundColor: 'red',
        clientId: 'client-1',
        groupId: 'folder-1',
        id: 'group-1',
        title: 'Test Group',
      },
      supervisorAgentId: 'agent-supervisor',
    });
    expect(result.group.createdAt).toBeInstanceOf(Date);
  });

  it('creates groups with members using snake_case REST body and camelCase result', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({
      agent_ids: ['member-1'],
      group_id: 'group-1',
      supervisor_agent_id: 'supervisor-1',
    });

    await expect(
      chatGroupService.createGroupWithMembers(
        { title: 'Team' },
        [{ backgroundColor: 'blue', systemRole: 'Analyze', title: 'Analyst' }],
        { systemRole: 'Coordinate', title: 'Supervisor' },
      ),
    ).resolves.toEqual({
      agentIds: ['member-1'],
      groupId: 'group-1',
      supervisorAgentId: 'supervisor-1',
    });

    expect(restClient.post).toHaveBeenCalledWith('/chat-groups/with-members', {
      body: {
        group_config: expect.objectContaining({ title: 'Team' }),
        members: [
          expect.objectContaining({
            background_color: 'blue',
            system_role: 'Analyze',
            title: 'Analyst',
          }),
        ],
        supervisor_config: expect.objectContaining({
          system_role: 'Coordinate',
          title: 'Supervisor',
        }),
      },
    });
  });

  it('loads group detail and marks supervisor agents', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      agents: [
        {
          background_color: 'green',
          created_at: '2026-05-01T10:00:00.000Z',
          id: 'agent-1',
          role: 'supervisor',
          system_role: 'Lead',
          updated_at: '2026-05-01T11:00:00.000Z',
        },
      ],
      created_at: '2026-05-01T10:00:00.000Z',
      id: 'group-1',
      title: 'Team',
      updated_at: '2026-05-01T11:00:00.000Z',
    });

    const detail = await chatGroupService.getGroupDetail('group-1');

    expect(restClient.get).toHaveBeenCalledWith('/chat-groups/group-1/detail');
    expect(detail).toMatchObject({
      agents: [
        {
          backgroundColor: 'green',
          id: 'agent-1',
          isSupervisor: true,
          systemRole: 'Lead',
        },
      ],
      id: 'group-1',
      supervisorAgentId: 'agent-1',
      title: 'Team',
    });
  });

  it('updates groups then refreshes the normalized group item', async () => {
    vi.mocked(restClient.put).mockResolvedValueOnce({ ok: true });
    vi.mocked(restClient.get).mockResolvedValueOnce({
      created_at: '2026-05-01T10:00:00.000Z',
      id: 'group-1',
      pinned: true,
      title: 'Pinned',
      updated_at: '2026-05-01T11:00:00.000Z',
    });

    await expect(chatGroupService.updateGroup('group-1', { pinned: true })).resolves.toMatchObject({
      id: 'group-1',
      pinned: true,
      title: 'Pinned',
    });

    expect(restClient.put).toHaveBeenCalledWith('/chat-groups/group-1', {
      body: expect.objectContaining({ pinned: true }),
    });
  });
});
