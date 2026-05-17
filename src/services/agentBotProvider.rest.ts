import { restClient } from '@/libs/rest';
import type { BotRuntimeStatusSnapshot } from '@/types/botRuntimeStatus';

class AgentBotProviderService {
  listPlatforms = async () => {
    return restClient.get('/agent-bot-providers/platforms/list');
  };

  getByAgentId = async (agentId: string) => {
    return restClient.get(`/agent-bot-providers/by-agent/${agentId}`);
  };

  getRuntimeStatus = async (_params: {
    applicationId: string;
    platform: string;
  }): Promise<BotRuntimeStatusSnapshot> => {
    // Runtime status requires the TS gateway infrastructure;
    // fallback to a basic status from the REST API
    return { status: 'unknown' } as BotRuntimeStatusSnapshot;
  };

  refreshRuntimeStatus = async (_params: {
    applicationId: string;
    platform: string;
  }): Promise<BotRuntimeStatusSnapshot> => {
    return { status: 'unknown' } as BotRuntimeStatusSnapshot;
  };

  refreshRuntimeStatusesByAgent = async (_agentId: string): Promise<void> => {
    // No-op in REST: gateway refresh requires TS infrastructure
  };

  create = async (params: {
    agentId: string;
    applicationId: string;
    credentials: Record<string, string>;
    enabled?: boolean;
    platform: string;
    settings?: Record<string, unknown>;
  }) => {
    return restClient.post('/agent-bot-providers', {
      body: {
        agent_id: params.agentId,
        application_id: params.applicationId,
        credentials: params.credentials,
        enabled: params.enabled,
        platform: params.platform,
        settings: params.settings,
      },
    });
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
  ) => {
    return restClient.patch(`/agent-bot-providers/${id}`, {
      body: {
        application_id: params.applicationId,
        credentials: params.credentials,
        enabled: params.enabled,
        platform: params.platform,
        settings: params.settings,
      },
    });
  };

  delete = async (id: string) => {
    return restClient.delete(`/agent-bot-providers/${id}`);
  };

  connectBot = async (params: {
    applicationId: string;
    platform: string;
  }): Promise<{ status: 'queued' | 'started' }> => {
    // Need to find provider ID from applicationId + platform first
    const providers = await restClient.get<any[]>('/agent-bot-providers', {
      params: { platform: params.platform } as any,
    });
    const provider = providers?.find?.((p: any) => p.application_id === params.applicationId);
    if (!provider) throw new Error('Bot provider not found');

    return restClient.post(`/agent-bot-providers/${provider.id}/connect`, {});
  };

  testConnection = async (params: { applicationId: string; platform: string }) => {
    const providers = await restClient.get<any[]>('/agent-bot-providers', {
      params: { platform: params.platform } as any,
    });
    const provider = providers?.find?.((p: any) => p.application_id === params.applicationId);
    if (!provider) throw new Error('Bot provider not found');

    return restClient.post(`/agent-bot-providers/${provider.id}/test`, {});
  };

  lineFetchBotInfo = async (_channelAccessToken: string) => {
    // LINE bot info fetch requires the TS LINE adapter
    throw new Error('lineFetchBotInfo is not available via REST API');
  };

  wechatGetQrCode = async () => {
    throw new Error('wechatGetQrCode is not available via REST API');
  };

  wechatPollQrStatus = async (_qrcode: string) => {
    // WeChat QR polling requires the TS WeChat adapter
    throw new Error('wechatPollQrStatus is not available via REST API');
  };
}

export const agentBotProviderService = new AgentBotProviderService();
