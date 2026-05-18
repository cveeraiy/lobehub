import { restClient } from '@/libs/rest';
import type { CreateKlavisServerParams, KlavisTool } from '@/store/tool/slices/klavisStore/types';

interface KlavisPlugin {
  customParams?: {
    klavis?: {
      instanceId: string;
      isAuthenticated: boolean;
      oauthUrl?: string;
      serverName: string;
      serverUrl: string;
    };
  };
  identifier: string;
  manifest?: {
    api?: Array<{
      description?: string;
      name: string;
      parameters?: KlavisTool['inputSchema'];
    }>;
  };
}

class KlavisService {
  createServerInstance = async (params: CreateKlavisServerParams) => {
    return restClient.post('/klavis/create-server-instance', {
      body: {
        identifier: params.identifier,
        server_name: params.serverName,
        user_id: params.userId,
      },
    });
  };

  deleteServerInstance = async (params: { identifier: string; instanceId: string }) => {
    return restClient.post('/klavis/delete-server-instance', {
      body: {
        identifier: params.identifier,
        instance_id: params.instanceId,
      },
    });
  };

  getKlavisPlugins = async (): Promise<KlavisPlugin[]> => {
    return restClient.get<KlavisPlugin[]>('/klavis/plugins');
  };

  getServerInstance = async (params: { instanceId: string }) => {
    return restClient.get('/klavis/server-instance', {
      params: { instanceId: params.instanceId },
    });
  };

  removeKlavisPlugin = async (params: { identifier: string }) => {
    return restClient.post('/klavis/remove-plugin', {
      body: { identifier: params.identifier },
    });
  };

  updateKlavisPlugin = async (params: {
    identifier: string;
    instanceId: string;
    isAuthenticated: boolean;
    oauthUrl?: string;
    serverName: string;
    serverUrl: string;
    tools: Array<{
      description?: string;
      inputSchema: KlavisTool['inputSchema'];
      name: string;
    }>;
  }) => {
    return restClient.post('/klavis/update-plugin', {
      body: {
        identifier: params.identifier,
        instance_id: params.instanceId,
        is_authenticated: params.isAuthenticated,
        oauth_url: params.oauthUrl,
        server_name: params.serverName,
        server_url: params.serverUrl,
        tools: params.tools,
      },
    });
  };
}

export const klavisService = new KlavisService();
