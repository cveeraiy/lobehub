import { type SidebarAgentItem, type SidebarAgentListResponse } from '@/database/repositories/home';
import { restClient } from '@/libs/rest';

export class HomeService {
  getSidebarAgentList = (): Promise<SidebarAgentListResponse> => {
    return restClient.get<SidebarAgentListResponse>('/home/sidebar-agents');
  };

  searchAgents = (keyword: string): Promise<SidebarAgentItem[]> => {
    return restClient.get<SidebarAgentItem[]>('/home/search-agents', {
      params: { keyword },
    });
  };

  updateAgentSessionGroupId = (agentId: string, sessionGroupId: string | null): Promise<void> => {
    return restClient.put('/home/agent-session-group', {
      body: { agentId, sessionGroupId },
    }) as any;
  };
}

export const homeService = new HomeService();
