import { type AgentGroupDetail } from '@lobechat/types';

import {
  type ChatGroupAgentItem,
  type ChatGroupItem,
  type NewChatGroup,
  type NewChatGroupAgent,
} from '@/database/schemas';
import { restClient } from '@/libs/rest';

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
  params?: any;
  provider?: string;
  systemRole?: string;
  tags?: string[];
  title?: string;
}

class ChatGroupService {
  getGroupByForkedFromIdentifier = async (forkedFromIdentifier: string): Promise<string | null> => {
    return restClient.get('/agent-groups/by-forked', { params: { forkedFromIdentifier } });
  };

  createGroup = (
    params: Omit<NewChatGroup, 'userId'>,
  ): Promise<{ group: ChatGroupItem; supervisorAgentId: string }> => {
    return restClient.post('/agent-groups', {
      body: { ...params, config: params.config as any },
    });
  };

  createGroupWithMembers = (
    groupConfig: Omit<NewChatGroup, 'userId'>,
    members: GroupMemberConfig[],
    supervisorConfig?: SupervisorConfig,
  ): Promise<{ agentIds: string[]; groupId: string; supervisorAgentId: string }> => {
    return restClient.post('/agent-groups/with-members', {
      body: {
        groupConfig: { ...groupConfig, config: groupConfig.config as any },
        members,
        supervisorConfig,
      },
    });
  };

  updateGroup = (id: string, value: Partial<ChatGroupItem>): Promise<ChatGroupItem> => {
    return restClient.put(`/agent-groups/${id}`, {
      body: { ...value, config: value.config as any },
    });
  };

  deleteGroup = (id: string) => {
    return restClient.delete(`/agent-groups/${id}`);
  };

  getGroup = (id: string): Promise<ChatGroupItem | undefined> => {
    return restClient.get(`/agent-groups/${id}`);
  };

  getGroupDetail = (id: string): Promise<AgentGroupDetail | null> => {
    return restClient.get(`/agent-groups/${id}/detail`);
  };

  getGroups = (): Promise<ChatGroupItem[]> => {
    return restClient.get('/agent-groups');
  };

  addAgentsToGroup = (
    groupId: string,
    agentIds: string[],
  ): Promise<{ added: NewChatGroupAgent[]; existing: string[] }> => {
    return restClient.post(`/agent-groups/${groupId}/agents`, { body: { agentIds } });
  };

  batchCreateAgentsInGroup = (groupId: string, agents: GroupMemberConfig[]) => {
    return restClient.post(`/agent-groups/${groupId}/agents/batch`, { body: { agents } });
  };

  removeAgentsFromGroup = (groupId: string, agentIds: string[]) => {
    return restClient.post(`/agent-groups/${groupId}/agents/remove`, { body: { agentIds } });
  };

  updateAgentInGroup = (
    groupId: string,
    agentId: string,
    updates: Partial<Pick<NewChatGroupAgent, 'order' | 'role'>>,
  ): Promise<NewChatGroupAgent> => {
    return restClient.put(`/agent-groups/${groupId}/agents/${agentId}`, {
      body: {
        order: updates.order === null ? undefined : updates.order,
        role: updates.role === null ? undefined : updates.role,
      },
    });
  };

  getGroupAgents = (groupId: string): Promise<ChatGroupAgentItem[]> => {
    return restClient.get(`/agent-groups/${groupId}/agents`);
  };

  duplicateGroup = (
    groupId: string,
    newTitle?: string,
  ): Promise<{ groupId: string; supervisorAgentId: string } | null> => {
    return restClient.post(`/agent-groups/${groupId}/duplicate`, { body: { newTitle } });
  };
}

export const chatGroupService = new ChatGroupService();
