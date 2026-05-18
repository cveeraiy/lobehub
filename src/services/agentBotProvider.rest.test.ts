import { beforeEach, describe, expect, it, vi } from 'vitest';

import { agentBotProviderService } from './agentBotProvider.rest';

const mockRestDelete = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPatch = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: mockRestDelete,
    get: mockRestGet,
    patch: mockRestPatch,
    post: mockRestPost,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AgentBotProviderService REST', () => {
  it('loads serialized platform definitions directly from Python', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        connectionMode: 'websocket',
        id: 'discord',
        name: 'Discord',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
      },
      {
        connectionMode: 'webhook',
        id: 'telegram',
        name: 'Telegram',
        schema: [{ key: 'credentials', label: 'channel.credentials', type: 'object' }],
      },
      {
        connectionMode: 'webhook',
        id: 'line',
        name: 'LINE',
        schema: [{ key: 'applicationId', label: 'channel.line.destinationUserId', type: 'string' }],
      },
      {
        connectionMode: 'websocket',
        id: 'slack',
        name: 'Slack',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
      },
      {
        connectionMode: 'websocket',
        id: 'feishu',
        name: 'Feishu',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
      },
      {
        connectionMode: 'websocket',
        id: 'lark',
        name: 'Lark',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
      },
      {
        connectionMode: 'websocket',
        id: 'qq',
        name: 'QQ',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
        supportsMessageEdit: false,
      },
      {
        connectionMode: 'polling',
        id: 'wechat',
        name: 'WeChat',
        schema: [{ key: 'settings', label: 'channel.settings', type: 'object' }],
        supportsMessageEdit: false,
      },
    ]);

    const result = await agentBotProviderService.listPlatforms();

    expect(mockRestGet).toHaveBeenCalledWith('/agent-bot-providers/platforms/list');
    expect(result).toEqual([
      {
        connectionMode: 'websocket',
        id: 'discord',
        name: 'Discord',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
      },
      {
        connectionMode: 'webhook',
        id: 'telegram',
        name: 'Telegram',
        schema: [{ key: 'credentials', label: 'channel.credentials', type: 'object' }],
      },
      {
        connectionMode: 'webhook',
        id: 'line',
        name: 'LINE',
        schema: [{ key: 'applicationId', label: 'channel.line.destinationUserId', type: 'string' }],
      },
      {
        connectionMode: 'websocket',
        id: 'slack',
        name: 'Slack',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
      },
      {
        connectionMode: 'websocket',
        id: 'feishu',
        name: 'Feishu',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
      },
      {
        connectionMode: 'websocket',
        id: 'lark',
        name: 'Lark',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
      },
      {
        connectionMode: 'websocket',
        id: 'qq',
        name: 'QQ',
        schema: [{ key: 'applicationId', label: 'channel.applicationId', type: 'string' }],
        supportsMarkdown: false,
        supportsMessageEdit: false,
      },
      {
        connectionMode: 'polling',
        id: 'wechat',
        name: 'WeChat',
        schema: [{ key: 'settings', label: 'channel.settings', type: 'object' }],
        supportsMessageEdit: false,
      },
    ]);
  });

  it('maps provider responses to the frontend service shape', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        agent_id: 'agent-1',
        application_id: 'app-1',
        credentials: { botToken: 'token' },
        enabled: true,
        id: 'provider-1',
        platform: 'discord',
        settings: { charLimit: 2000 },
        user_id: 'user-1',
      },
    ]);

    const result = await agentBotProviderService.getByAgentId('agent-1');

    expect(mockRestGet).toHaveBeenCalledWith('/agent-bot-providers/by-agent/agent-1');
    expect(result).toEqual([
      {
        agentId: 'agent-1',
        applicationId: 'app-1',
        credentials: { botToken: 'token' },
        enabled: true,
        id: 'provider-1',
        platform: 'discord',
        settings: { charLimit: 2000 },
        userId: 'user-1',
      },
    ]);
  });

  it('creates providers with Python snake_case request fields', async () => {
    mockRestPost.mockResolvedValueOnce({
      agent_id: 'agent-1',
      application_id: 'app-1',
      credentials: { botToken: 'token', publicKey: 'key' },
      enabled: true,
      id: 'provider-1',
      platform: 'discord',
      settings: { charLimit: 2000 },
    });

    const result = await agentBotProviderService.create({
      agentId: 'agent-1',
      applicationId: 'app-1',
      credentials: { botToken: 'token', publicKey: 'key' },
      platform: 'discord',
      settings: { charLimit: 2000 },
    });

    expect(mockRestPost).toHaveBeenCalledWith('/agent-bot-providers', {
      body: {
        agent_id: 'agent-1',
        application_id: 'app-1',
        credentials: { botToken: 'token', publicKey: 'key' },
        enabled: undefined,
        platform: 'discord',
        settings: { charLimit: 2000 },
      },
    });
    expect(result.applicationId).toBe('app-1');
  });

  it('uses normalized providers when connecting or testing a bot', async () => {
    mockRestGet.mockResolvedValue([
      {
        application_id: 'app-1',
        credentials: {},
        enabled: true,
        id: 'provider-1',
        platform: 'discord',
      },
    ]);
    mockRestPost.mockResolvedValueOnce({ valid: true }).mockResolvedValueOnce({ status: 'queued' });

    await agentBotProviderService.testConnection({ applicationId: 'app-1', platform: 'discord' });
    await agentBotProviderService.connectBot({ applicationId: 'app-1', platform: 'discord' });

    expect(mockRestPost).toHaveBeenNthCalledWith(1, '/agent-bot-providers/provider-1/test', {});
    expect(mockRestPost).toHaveBeenNthCalledWith(2, '/agent-bot-providers/provider-1/connect', {});
  });

  it('maps runtime status responses', async () => {
    mockRestGet.mockResolvedValueOnce({
      application_id: 'app-1',
      platform: 'discord',
      status: 'disconnected',
      updated_at: 123,
    });

    const result = await agentBotProviderService.getRuntimeStatus({
      applicationId: 'app-1',
      platform: 'discord',
    });

    expect(mockRestGet).toHaveBeenCalledWith('/agent-bot-providers/runtime-status/get', {
      params: { application_id: 'app-1', platform: 'discord' },
    });
    expect(result).toEqual({
      applicationId: 'app-1',
      errorMessage: undefined,
      platform: 'discord',
      status: 'disconnected',
      updatedAt: 123,
    });
  });

  it('deletes providers through REST', async () => {
    mockRestDelete.mockResolvedValueOnce({ success: true });

    await agentBotProviderService.delete('provider-1');

    expect(mockRestDelete).toHaveBeenCalledWith('/agent-bot-providers/provider-1');
  });

  it('fetches LINE bot info through REST and maps the response', async () => {
    mockRestPost.mockResolvedValueOnce({
      basic_id: '@line-basic',
      display_name: 'Line Bot',
      user_id: 'U123',
    });

    const result = await agentBotProviderService.lineFetchBotInfo('line-token');

    expect(mockRestPost).toHaveBeenCalledWith('/agent-bot-providers/line/fetch-bot-info', {
      body: { channel_access_token: 'line-token' },
    });
    expect(result).toEqual({
      basicId: '@line-basic',
      displayName: 'Line Bot',
      userId: 'U123',
    });
  });
});
