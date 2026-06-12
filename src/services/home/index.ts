import { restClient } from '@/libs/rest';
import { type SidebarAgentItem, type SidebarAgentListResponse } from '@/types/home';

type RawSidebarAgentItem = Omit<SidebarAgentItem, 'updatedAt'> & {
  updatedAt?: string | null;
};

type RawSidebarGroup = Omit<SidebarAgentListResponse['groups'][number], 'items'> & {
  agents?: RawSidebarAgentItem[];
  items?: RawSidebarAgentItem[];
};

interface RawSidebarAgentListResponse {
  groups: RawSidebarGroup[];
  pinned: RawSidebarAgentItem[];
  ungrouped: RawSidebarAgentItem[];
}

const toSidebarAgentItem = (item: RawSidebarAgentItem): SidebarAgentItem => ({
  ...item,
  updatedAt: item.updatedAt ? new Date(item.updatedAt) : new Date(0),
});

const toSidebarAgentListResponse = (
  response: RawSidebarAgentListResponse,
): SidebarAgentListResponse => ({
  groups: response.groups.map((group) => ({
    id: group.id,
    items: (group.items ?? group.agents ?? []).map(toSidebarAgentItem),
    name: group.name,
    sort: group.sort,
  })),
  pinned: response.pinned.map(toSidebarAgentItem),
  ungrouped: response.ungrouped.map(toSidebarAgentItem),
});

export class HomeService {
  getSidebarAgentList = async (): Promise<SidebarAgentListResponse> => {
    const response = await restClient.get<RawSidebarAgentListResponse>('/home/sidebar-agents');
    return toSidebarAgentListResponse(response);
  };

  searchAgents = async (keyword: string): Promise<SidebarAgentItem[]> => {
    const response = await restClient.get<RawSidebarAgentItem[]>('/home/search-agents', {
      params: { keyword },
    });
    return response.map(toSidebarAgentItem);
  };

  updateAgentSessionGroupId = (agentId: string, sessionGroupId: string | null): Promise<void> => {
    return restClient.put('/home/agent-group', {
      body: { agent_id: agentId, session_group_id: sessionGroupId },
    }) as any;
  };
}

export const homeService = new HomeService();
