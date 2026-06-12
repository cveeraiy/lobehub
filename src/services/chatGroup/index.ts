import type { AgentGroupDetail, AgentGroupMember } from '@lobechat/types';

import { restClient } from '@/libs/rest';
import type {
  ChatGroupAgentItem,
  ChatGroupItem,
  NewChatGroup,
  NewChatGroupAgent,
} from '@/types/chatGroup';

export interface GroupMemberConfig {
  avatar?: string;
  backgroundColor?: string;
  description?: string;
  model?: string;
  plugins?: string[];
  provider?: string;
  systemRole?: string;
  tags?: string[];
  title?: string;
}

export interface SupervisorConfig {
  avatar?: string;
  backgroundColor?: string;
  description?: string;
  model?: string;
  params?: unknown;
  provider?: string;
  systemRole?: string;
  tags?: string[];
  title?: string;
}

export interface BatchCreateAgentsResult {
  agentIds?: string[];
  agents: Array<{ id: string; title?: string | null }>;
}

interface RawChatGroupItem extends Partial<ChatGroupItem> {
  background_color?: string | null;
  client_id?: string | null;
  created_at?: string | null;
  editor_data?: ChatGroupItem['editorData'] | null;
  group_id?: string | null;
  market_identifier?: string | null;
  name?: string | null;
  updated_at?: string | null;
}

interface RawChatGroupAgentItem extends Partial<ChatGroupAgentItem> {
  agent_id?: string;
  chat_group_id?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

interface RawGroupDetail extends RawChatGroupItem {
  agents?: RawAgentGroupMember[];
  supervisor_agent_id?: string | null;
  supervisorAgentId?: string | null;
}

interface RawAgentGroupMember extends Partial<AgentGroupMember> {
  agent_id?: string;
  background_color?: string | null;
  chat_group_id?: string;
  created_at?: string | null;
  id: string;
  role?: string | null;
  system_role?: string | null;
  updated_at?: string | null;
  user_id?: string;
}

const toDate = (value?: Date | string | null) => {
  if (value instanceof Date) return value;
  return value ? new Date(value) : new Date(0);
};

const toGroupBody = (value: Partial<ChatGroupItem | NewChatGroup>) => ({
  avatar: value.avatar,
  background_color: value.backgroundColor,
  client_id: value.clientId,
  config: value.config,
  content: value.content,
  description: value.description,
  editor_data: value.editorData,
  group_id: value.groupId,
  id: value.id,
  market_identifier: value.marketIdentifier,
  pinned: value.pinned,
  title: value.title,
});

const toAgentBody = (agent: GroupMemberConfig) => ({
  ...agent,
  background_color: agent.backgroundColor,
  system_role: agent.systemRole,
});

const toGroup = (group: RawChatGroupItem): ChatGroupItem => {
  const title = group.title ?? group.name ?? null;

  return {
    ...group,
    backgroundColor: group.backgroundColor ?? group.background_color ?? null,
    clientId: group.clientId ?? group.client_id ?? null,
    createdAt: toDate(group.createdAt ?? group.created_at),
    editorData: group.editorData ?? group.editor_data ?? null,
    groupId: group.groupId ?? group.group_id ?? null,
    id: group.id!,
    marketIdentifier: group.marketIdentifier ?? group.market_identifier ?? null,
    title,
    updatedAt: toDate(group.updatedAt ?? group.updated_at),
    userId: group.userId ?? '',
  } as ChatGroupItem;
};

const toGroupAgent = (agent: RawChatGroupAgentItem): NewChatGroupAgent => ({
  ...agent,
  agentId: agent.agentId ?? agent.agent_id!,
  chatGroupId: agent.chatGroupId ?? agent.chat_group_id!,
  createdAt: toDate(agent.createdAt ?? agent.created_at),
  updatedAt: toDate(agent.updatedAt ?? agent.updated_at),
  userId: agent.userId ?? '',
});

const toGroupAgentsResult = (response: {
  added?: RawChatGroupAgentItem[];
  existing?: string[];
}): { added: NewChatGroupAgent[]; existing: string[] } => ({
  added: (response.added ?? []).map(toGroupAgent),
  existing: response.existing ?? [],
});

const toGroupDetail = (detail: RawGroupDetail | null): AgentGroupDetail | null => {
  if (!detail) return null;

  const group = toGroup(detail);
  const agents = (detail.agents ?? []).map((agent) => ({
    ...agent,
    backgroundColor: agent.backgroundColor ?? agent.background_color ?? null,
    createdAt: toDate(agent.createdAt ?? agent.created_at),
    isSupervisor: agent.isSupervisor === true || agent.role === 'supervisor',
    systemRole: agent.systemRole ?? agent.system_role ?? null,
    updatedAt: toDate(agent.updatedAt ?? agent.updated_at),
    userId: agent.userId ?? agent.user_id ?? '',
  })) as AgentGroupMember[];

  return {
    ...group,
    agents,
    supervisorAgentId:
      detail.supervisorAgentId ??
      detail.supervisor_agent_id ??
      agents.find((agent) => agent.isSupervisor)?.id,
  } as AgentGroupDetail;
};

class ChatGroupService {
  getGroupByForkedFromIdentifier = async (forkedFromIdentifier: string): Promise<string | null> => {
    return restClient.get<string | null>(
      `/chat-groups/by-forked-from/${encodeURIComponent(forkedFromIdentifier)}`,
    );
  };

  createGroup = async (
    params: Omit<NewChatGroup, 'userId'>,
  ): Promise<{ group: ChatGroupItem; supervisorAgentId: string }> => {
    const response = await restClient.post<{
      group: RawChatGroupItem;
      supervisor_agent_id?: string;
      supervisorAgentId?: string;
    }>('/chat-groups', {
      body: toGroupBody(params),
    });

    return {
      group: toGroup(response.group),
      supervisorAgentId: response.supervisorAgentId ?? response.supervisor_agent_id!,
    };
  };

  createGroupWithMembers = async (
    groupConfig: Omit<NewChatGroup, 'userId'>,
    members: GroupMemberConfig[],
    supervisorConfig?: SupervisorConfig,
  ): Promise<{ agentIds: string[]; groupId: string; supervisorAgentId: string }> => {
    const response = await restClient.post<{
      agent_ids?: string[];
      agentIds?: string[];
      group_id?: string;
      groupId?: string;
      supervisor_agent_id?: string;
      supervisorAgentId?: string;
    }>('/chat-groups/with-members', {
      body: {
        group_config: toGroupBody(groupConfig),
        members: members.map(toAgentBody),
        supervisor_config: supervisorConfig ? toAgentBody(supervisorConfig) : undefined,
      },
    });

    return {
      agentIds: response.agentIds ?? response.agent_ids ?? [],
      groupId: response.groupId ?? response.group_id!,
      supervisorAgentId: response.supervisorAgentId ?? response.supervisor_agent_id!,
    };
  };

  updateGroup = async (id: string, value: Partial<ChatGroupItem>): Promise<ChatGroupItem> => {
    await restClient.put(`/chat-groups/${id}`, {
      body: toGroupBody(value),
    });

    const group = await this.getGroup(id);
    return group!;
  };

  deleteGroup = (id: string) => {
    return restClient.delete(`/chat-groups/${id}`);
  };

  getGroup = (id: string): Promise<ChatGroupItem | undefined> => {
    return restClient.get<RawChatGroupItem>(`/chat-groups/${id}`).then(toGroup);
  };

  getGroupDetail = (id: string): Promise<AgentGroupDetail | null> => {
    return restClient.get<RawGroupDetail>(`/chat-groups/${id}/detail`).then(toGroupDetail);
  };

  getGroups = (): Promise<ChatGroupItem[]> => {
    return restClient.get<RawChatGroupItem[]>('/chat-groups').then((groups) => groups.map(toGroup));
  };

  addAgentsToGroup = async (
    groupId: string,
    agentIds: string[],
  ): Promise<{ added: NewChatGroupAgent[]; existing: string[] }> => {
    const response = await restClient.post<{
      added?: RawChatGroupAgentItem[];
      existing?: string[];
    }>(`/chat-groups/${groupId}/agents`, { body: { agent_ids: agentIds } });
    return toGroupAgentsResult(response);
  };

  batchCreateAgentsInGroup = async (
    groupId: string,
    agents: GroupMemberConfig[],
  ): Promise<BatchCreateAgentsResult> => {
    const response = await restClient.post<{
      agent_ids?: string[];
      agentIds?: string[];
      agents: Array<{ id: string; title?: string | null }>;
    }>(`/chat-groups/${groupId}/agents/batch-create`, {
      body: { agents: agents.map(toAgentBody), group_id: groupId },
    });

    return {
      agentIds: response.agentIds ?? response.agent_ids,
      agents: response.agents,
    };
  };

  removeAgentsFromGroup = (groupId: string, agentIds: string[]) => {
    return restClient.post(`/chat-groups/${groupId}/agents/remove`, {
      body: { agent_ids: agentIds },
    });
  };

  updateAgentInGroup = async (
    groupId: string,
    agentId: string,
    updates: Partial<Pick<NewChatGroupAgent, 'order' | 'role'>>,
  ): Promise<NewChatGroupAgent> => {
    await restClient.put(`/chat-groups/${groupId}/agents/${agentId}`, {
      body: {
        order: updates.order === null ? undefined : updates.order,
        role: updates.role === null ? undefined : updates.role,
      },
    });

    const agents = await this.getGroupAgents(groupId);
    return agents.find((agent) => agent.agentId === agentId)!;
  };

  getGroupAgents = (groupId: string): Promise<ChatGroupAgentItem[]> => {
    return restClient
      .get<RawChatGroupAgentItem[]>(`/chat-groups/${groupId}/agents`)
      .then((agents) => agents.map(toGroupAgent) as ChatGroupAgentItem[]);
  };

  duplicateGroup = async (
    groupId: string,
    newTitle?: string,
  ): Promise<{ groupId: string; supervisorAgentId: string } | null> => {
    const response = await restClient.post<{
      group_id?: string;
      groupId?: string;
      id?: string;
      supervisor_agent_id?: string | null;
      supervisorAgentId?: string | null;
    }>(`/chat-groups/${groupId}/duplicate`, { body: { new_title: newTitle } });

    return response
      ? {
          groupId: response.groupId ?? response.group_id ?? response.id!,
          supervisorAgentId: response.supervisorAgentId ?? response.supervisor_agent_id ?? '',
        }
      : null;
  };
}

export const chatGroupService = new ChatGroupService();
