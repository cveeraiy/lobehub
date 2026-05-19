import { restClient } from '@/libs/rest';
import type { SerializedPlatformDefinition } from '@/server/services/bot/platforms/types';
import type { BotRuntimeStatusSnapshot } from '@/types/botRuntimeStatus';

interface AgentBotProviderResponse {
  agent_id: string;
  application_id: string;
  created_at?: string | null;
  credentials: Record<string, string> | null;
  enabled: boolean;
  id: string;
  platform: string;
  runtime_status?: BotRuntimeStatusSnapshot['status'];
  settings?: Record<string, unknown> | null;
  updated_at?: string | null;
  user_id?: string;
}

interface BotProviderItem {
  agentId: string;
  applicationId: string;
  createdAt?: string | null;
  credentials: Record<string, string>;
  enabled: boolean;
  id: string;
  platform: string;
  runtimeStatus?: BotRuntimeStatusSnapshot['status'];
  settings?: Record<string, unknown> | null;
  updatedAt?: string | null;
  userId?: string;
}

interface RuntimeStatusResponse {
  application_id: string;
  error_message?: string;
  platform: string;
  status: BotRuntimeStatusSnapshot['status'];
  updated_at: number;
}

const mapProvider = (item: AgentBotProviderResponse): BotProviderItem => ({
  agentId: item.agent_id,
  applicationId: item.application_id,
  createdAt: item.created_at,
  credentials: item.credentials ?? {},
  enabled: item.enabled,
  id: item.id,
  platform: item.platform,
  runtimeStatus: item.runtime_status,
  settings: item.settings,
  updatedAt: item.updated_at,
  userId: item.user_id,
});

const mapRuntimeStatus = (item: RuntimeStatusResponse): BotRuntimeStatusSnapshot => ({
  applicationId: item.application_id,
  errorMessage: item.error_message,
  platform: item.platform,
  status: item.status,
  updatedAt: item.updated_at,
});

class AgentBotProviderService {
  listPlatforms = async (): Promise<SerializedPlatformDefinition[]> => {
    return restClient.get<SerializedPlatformDefinition[]>('/agent-bot-providers/platforms/list');
  };

  list = async (): Promise<BotProviderItem[]> => {
    const result = await restClient.get<AgentBotProviderResponse[]>('/agent-bot-providers');
    return result.map(mapProvider);
  };

  getByAgentId = async (agentId: string): Promise<BotProviderItem[]> => {
    const result = await restClient.get<AgentBotProviderResponse[]>(
      `/agent-bot-providers/by-agent/${agentId}`,
    );
    return result.map(mapProvider);
  };

  getRuntimeStatus = async (params: {
    applicationId: string;
    platform: string;
  }): Promise<BotRuntimeStatusSnapshot> => {
    const result = await restClient.get<RuntimeStatusResponse>(
      '/agent-bot-providers/runtime-status/get',
      {
        params: {
          application_id: params.applicationId,
          platform: params.platform,
        },
      },
    );
    return mapRuntimeStatus(result);
  };

  refreshRuntimeStatus = async (params: {
    applicationId: string;
    platform: string;
  }): Promise<BotRuntimeStatusSnapshot> => {
    const result = await restClient.post<RuntimeStatusResponse>(
      '/agent-bot-providers/runtime-status/refresh',
      {
        body: {
          application_id: params.applicationId,
          platform: params.platform,
        },
      },
    );
    return mapRuntimeStatus(result);
  };

  refreshRuntimeStatusesByAgent = async (agentId: string): Promise<void> => {
    await restClient.post(`/agent-bot-providers/runtime-status/refresh-by-agent/${agentId}`, {});
  };

  create = async (params: {
    agentId: string;
    applicationId: string;
    credentials: Record<string, string>;
    enabled?: boolean;
    platform: string;
    settings?: Record<string, unknown>;
  }): Promise<BotProviderItem> => {
    const result = await restClient.post<AgentBotProviderResponse>('/agent-bot-providers', {
      body: {
        agent_id: params.agentId,
        application_id: params.applicationId,
        credentials: params.credentials,
        enabled: params.enabled,
        platform: params.platform,
        settings: params.settings,
      },
    });
    return mapProvider(result);
  };

  update = async (
    id: string,
    params: {
      applicationId?: string;
      credentials?: Record<string, string>;
      enabled?: boolean;
      platform?: string;
      settings?: Record<string, unknown>;
    },
  ): Promise<BotProviderItem> => {
    const result = await restClient.patch<AgentBotProviderResponse>(`/agent-bot-providers/${id}`, {
      body: {
        application_id: params.applicationId,
        credentials: params.credentials,
        enabled: params.enabled,
        platform: params.platform,
        settings: params.settings,
      },
    });
    return mapProvider(result);
  };

  delete = async (id: string) => {
    return restClient.delete(`/agent-bot-providers/${id}`);
  };

  connectBot = async (params: {
    applicationId: string;
    platform: string;
  }): Promise<{ status: 'connected' | 'connecting' | 'queued' | 'started' }> => {
    const providers = await this.list();
    const provider = providers.find(
      (item) => item.applicationId === params.applicationId && item.platform === params.platform,
    );
    if (!provider) throw new Error('Bot provider not found');

    return restClient.post(`/agent-bot-providers/${provider.id}/connect`, {});
  };

  testConnection = async (params: { applicationId: string; platform: string }) => {
    const providers = await this.list();
    const provider = providers.find(
      (item) => item.applicationId === params.applicationId && item.platform === params.platform,
    );
    if (!provider) throw new Error('Bot provider not found');

    return restClient.post(`/agent-bot-providers/${provider.id}/test`, {});
  };

  lineFetchBotInfo = async (
    channelAccessToken: string,
  ): Promise<{ basicId?: string; displayName?: string; userId: string }> => {
    const result = await restClient.post<{
      basic_id?: string;
      display_name?: string;
      user_id: string;
    }>('/agent-bot-providers/line/fetch-bot-info', {
      body: { channel_access_token: channelAccessToken },
    });
    return {
      basicId: result.basic_id,
      displayName: result.display_name,
      userId: result.user_id,
    };
  };

  wechatGetQrCode = async () => {
    throw new Error('wechatGetQrCode is not available via REST API');
  };

  wechatPollQrStatus = async (_qrcode: string) => {
    throw new Error('wechatPollQrStatus is not available via REST API');
  };
}

export const agentBotProviderService = new AgentBotProviderService();
