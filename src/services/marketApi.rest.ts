import {
  type AgentCreateResponse,
  type AgentItemDetail,
  type AgentListResponse,
} from '@lobehub/market-sdk';

import { restClient } from '@/libs/rest';
import { discoverService } from '@/services/discover';
import {
  type AgentForkRequest,
  type AgentForkResponse,
  type AgentForkSourceResponse,
  type AgentForksResponse,
  type AgentGroupForkRequest,
  type AgentGroupForkResponse,
  type AgentGroupForkSourceResponse,
  type AgentGroupForksResponse,
  type SkillSorts,
} from '@/types/discover';

interface GetOwnAgentsParams {
  page?: number;
  pageSize?: number;
}

interface AgentOwnershipResult {
  exists: boolean;
  isOwner: boolean;
  originalAgent: unknown | null;
}

interface AgentGroupOwnershipResult {
  exists: boolean;
  isOwner: boolean;
  originalGroup: unknown | null;
}

interface PublishAgentResult {
  identifier: string;
  isNewAgent: boolean;
  success: boolean;
}

interface PublishAgentGroupResult {
  identifier: string;
  isNewGroup: boolean;
  success: boolean;
}

export class MarketApiService {
  /**
   * @deprecated No-op: Authentication is now handled through REST auth headers.
   */
  setAccessToken(_token: string) {
    // No-op
  }

  // Create new agent
  async createAgent(agentData: {
    homepage?: string;
    identifier: string;
    isFeatured?: boolean;
    name: string;
    status?: 'published' | 'unpublished' | 'archived' | 'deprecated';
    tokenUsage?: number;
    visibility?: 'public' | 'private' | 'internal';
  }): Promise<AgentCreateResponse> {
    return restClient.post('/market/agent', { body: agentData });
  }

  // Get agent detail by identifier
  async getAgentDetail(
    identifier: string,
  ): Promise<AgentItemDetail & { forkedFromAgentId?: string }> {
    return restClient.get('/market/agent/detail', {
      params: { identifier },
    }) as Promise<AgentItemDetail>;
  }

  // Check if agent exists (returns true if exists, false if not)
  async checkAgentExists(identifier: string): Promise<boolean> {
    try {
      await this.getAgentDetail(identifier);
      return true;
    } catch {
      return false;
    }
  }

  async checkAgentOwnership(identifier: string): Promise<AgentOwnershipResult> {
    return restClient.get('/market/agent/check-ownership', { params: { identifier } });
  }

  async publishOrCreateAgent(params: Record<string, any>): Promise<PublishAgentResult> {
    return restClient.post('/market/agent/publish-or-create', {
      body: {
        ...params,
        editor_data: params.editorData,
        token_usage: params.tokenUsage,
      },
    });
  }

  // Create agent version
  async createAgentVersion(versionData: {
    a2aProtocolVersion?: string;
    avatar?: string;
    category?: string;
    changelog?: string;
    config?: Record<string, any>;
    defaultInputModes?: string[];
    defaultOutputModes?: string[];
    description?: string;
    documentationUrl?: string;
    extensions?: Record<string, any>[];
    hasPushNotifications?: boolean;
    hasStateTransitionHistory?: boolean;
    hasStreaming?: boolean;
    identifier: string;
    interfaces?: Record<string, any>[];
    name?: string;
    preferredTransport?: string;
    providerId?: number;
    securityRequirements?: Record<string, any>[];
    securitySchemes?: Record<string, any>;
    setAsCurrent?: boolean;
    summary?: string;
    supportsAuthenticatedExtendedCard?: boolean;
    tokenUsage?: number;
    url?: string;
  }) {
    return restClient.post('/market/agent/version', { body: versionData });
  }

  // Publish agent
  async publishAgent(identifier: string): Promise<void> {
    await restClient.post('/market/agent/publish', { body: { identifier } });
  }

  // Unpublish agent
  async unpublishAgent(identifier: string): Promise<void> {
    await restClient.post('/market/agent/unpublish', { body: { identifier } });
  }

  // Deprecate agent
  async deprecateAgent(identifier: string): Promise<void> {
    await restClient.post('/market/agent/deprecate', { body: { identifier } });
  }

  // Get own agents
  async getOwnAgents(params?: GetOwnAgentsParams): Promise<AgentListResponse> {
    return restClient.get('/market/agent/own', {
      params: params as any,
    }) as Promise<AgentListResponse>;
  }

  // ==================== Fork Agent API ====================

  async forkAgent(
    sourceIdentifier: string,
    forkData: AgentForkRequest,
  ): Promise<AgentForkResponse> {
    return restClient.post('/market/agent/fork', {
      body: { sourceIdentifier, ...forkData },
    });
  }

  async getAgentForks(identifier: string): Promise<AgentForksResponse> {
    return restClient.get('/market/agent/forks', { params: { identifier } });
  }

  async getAgentForkSource(identifier: string): Promise<AgentForkSourceResponse> {
    return restClient.get('/market/agent/fork-source', { params: { identifier } });
  }

  // ==================== Agent Group Status Management ====================

  async getAgentGroupDetail(identifier: string): Promise<any> {
    return restClient.get('/market/agent-group/detail', { params: { identifier } }) as Promise<any>;
  }

  async checkAgentGroupOwnership(identifier: string): Promise<AgentGroupOwnershipResult> {
    return restClient.get('/market/agent-group/check-ownership', { params: { identifier } });
  }

  async publishOrCreateAgentGroup(params: Record<string, any>): Promise<PublishAgentGroupResult> {
    return restClient.post('/market/agent-group/publish-or-create', {
      body: {
        ...params,
        background_color: params.backgroundColor,
        member_agents: params.memberAgents,
      },
    });
  }

  async publishAgentGroup(identifier: string): Promise<void> {
    await restClient.post('/market/agent-group/publish', { body: { identifier } });
  }

  async unpublishAgentGroup(identifier: string): Promise<void> {
    await restClient.post('/market/agent-group/unpublish', { body: { identifier } });
  }

  async deprecateAgentGroup(identifier: string): Promise<void> {
    await restClient.post('/market/agent-group/deprecate', { body: { identifier } });
  }

  // ==================== Fork Agent Group API ====================

  async forkAgentGroup(
    sourceIdentifier: string,
    forkData: AgentGroupForkRequest,
  ): Promise<AgentGroupForkResponse> {
    return restClient.post('/market/agent-group/fork', {
      body: { sourceIdentifier, ...forkData },
    });
  }

  async getAgentGroupForks(identifier: string): Promise<AgentGroupForksResponse> {
    return restClient.get('/market/agent-group/forks', { params: { identifier } });
  }

  async getAgentGroupForkSource(identifier: string): Promise<AgentGroupForkSourceResponse> {
    return restClient.get('/market/agent-group/fork-source', { params: { identifier } });
  }

  // ==================== Skills API ====================

  async listCreds() {
    return restClient.get('/market/creds/list');
  }

  async searchSkill(params: {
    category?: string;
    locale?: string;
    order?: 'asc' | 'desc';
    page?: number;
    pageSize?: number;
    q?: string;
    sort?: SkillSorts;
  }) {
    await discoverService.safeInjectMPToken();

    return restClient.get('/market/skill/list', { params: params as any });
  }

  getSkillDownloadUrl(identifier: string): string {
    const marketBaseUrl = process.env.NEXT_PUBLIC_MARKET_BASE_URL || 'https://market.lobehub.com';
    return `${marketBaseUrl}/api/v1/skills/${identifier}/download`;
  }
}

export const marketApiService = new MarketApiService();
