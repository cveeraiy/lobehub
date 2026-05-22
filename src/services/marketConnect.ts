import { restClient } from '@/libs/rest';

interface AuthorizeParams {
  provider: string;
  redirectUri?: string;
  scopes?: string[];
}

interface ProviderParams {
  provider: string;
}

interface CallToolParams {
  args?: Record<string, unknown>;
  provider: string;
  toolName: string;
  topicId?: string;
}

interface ConnectionStatus {
  connected: boolean;
  connection?: {
    providerUsername?: string;
    scopes?: string[];
    tokenExpiresAt?: string;
  };
  icon?: string;
  providerName?: string;
}

interface AuthorizeResponse {
  authorizeUrl: string;
  code: string;
  expiresIn: number;
}

interface ConnectionsResponse {
  connections: Array<Record<string, any>>;
}

interface ProvidersResponse {
  providers: Array<Record<string, any>>;
}

interface ToolsResponse {
  provider?: string;
  tools: Array<Record<string, any>>;
}

interface RefreshResponse {
  connection?: {
    tokenExpiresAt?: string;
  };
  refreshed: boolean;
}

interface CallToolResponse {
  data?: unknown;
  success: boolean;
}

class MarketConnectService {
  callTool = async (params: CallToolParams): Promise<CallToolResponse> => {
    return restClient.post<CallToolResponse>('/market/connect/tool', { body: params });
  };

  getAllHealth = async () => {
    return restClient.get('/market/connect/health');
  };

  getAuthorizeUrl = async (params: AuthorizeParams): Promise<AuthorizeResponse> => {
    return restClient.post<AuthorizeResponse>('/market/connect/authorize', { body: params });
  };

  getStatus = async (params: ProviderParams): Promise<ConnectionStatus> => {
    return restClient.get<ConnectionStatus>('/market/connect/status', {
      params: { provider: params.provider },
    });
  };

  listConnections = async (): Promise<ConnectionsResponse> => {
    return restClient.get<ConnectionsResponse>('/market/connect/connections');
  };

  listProviders = async (): Promise<ProvidersResponse> => {
    return restClient.get<ProvidersResponse>('/market/connect/providers');
  };

  listTools = async (params: ProviderParams): Promise<ToolsResponse> => {
    return restClient.get<ToolsResponse>('/market/connect/tools', {
      params: { provider: params.provider },
    });
  };

  refresh = async (params: ProviderParams): Promise<RefreshResponse> => {
    return restClient.post<RefreshResponse>('/market/connect/refresh', { body: params });
  };

  revoke = async (params: ProviderParams) => {
    return restClient.post('/market/connect/revoke', { body: params });
  };
}

export const marketConnectService = new MarketConnectService();
