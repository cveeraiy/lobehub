import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { businessService } from '../business';
import { cloudSandboxService } from '../cloudSandbox';
import { credsService } from '../creds';
import { deviceService } from '../device';
import { generationWorkerService } from '../generationWorker';
import { klavisService } from '../klavis';
import { marketConnectService } from '../marketConnect';
import { oauthDeviceFlowService } from '../oauthDeviceFlow';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('frontend REST parity services', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses Python OAuth device-flow endpoints', async () => {
    await oauthDeviceFlowService.getAuthStatus('githubcopilot');
    await oauthDeviceFlowService.initiateDeviceCode('githubcopilot');
    await oauthDeviceFlowService.pollAuthStatus({
      deviceCode: 'device-code',
      providerId: 'githubcopilot',
    });
    await oauthDeviceFlowService.revokeAuth('githubcopilot');

    expect(restClient.get).toHaveBeenCalledWith('/oauth-device-flow/auth-status', {
      params: { provider_id: 'githubcopilot' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/oauth-device-flow/initiate-device-code', {
      body: { providerId: 'githubcopilot' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/oauth-device-flow/poll-auth-status', {
      body: { deviceCode: 'device-code', providerId: 'githubcopilot' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/oauth-device-flow/revoke-auth', {
      body: { providerId: 'githubcopilot' },
    });
  });

  it('covers market credential execution helpers', async () => {
    await credsService.deleteByKey('github');
    await credsService.getByKey('github', { decrypt: true });
    await credsService.getSkillCredStatus('skill-1');
    await credsService.inject({ keys: ['github'], topicId: 'topic-1' });
    await credsService.injectForSkill({ sandbox: true, skillIdentifier: 'github' });

    expect(restClient.delete).toHaveBeenCalledWith('/market/creds/by-key/github');
    expect(restClient.get).toHaveBeenCalledWith('/market/creds/by-key/github', {
      params: { decrypt: true },
    });
    expect(restClient.get).toHaveBeenCalledWith('/market/creds/skill-status', {
      params: { keys: 'skill-1' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/market/creds/inject', {
      body: { keys: ['github'], topicId: 'topic-1' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/market/creds/inject-for-skill', {
      body: { sandbox: true, skillIdentifier: 'github' },
    });
  });

  it('covers market connect REST helpers', async () => {
    await marketConnectService.callTool({
      args: { issue: '123' },
      provider: 'linear',
      toolName: 'getIssue',
      topicId: 'topic-1',
    });
    await marketConnectService.getAuthorizeUrl({
      provider: 'linear',
      redirectUri: 'https://app.example.test/oauth',
      scopes: ['read'],
    });
    await marketConnectService.getStatus({ provider: 'linear' });
    await marketConnectService.listConnections();
    await marketConnectService.listProviders();
    await marketConnectService.listTools({ provider: 'linear' });
    await marketConnectService.refresh({ provider: 'linear' });
    await marketConnectService.revoke({ provider: 'linear' });

    expect(restClient.post).toHaveBeenCalledWith('/market/connect/tool', {
      body: {
        args: { issue: '123' },
        provider: 'linear',
        toolName: 'getIssue',
        topicId: 'topic-1',
      },
    });
    expect(restClient.post).toHaveBeenCalledWith('/market/connect/authorize', {
      body: {
        provider: 'linear',
        redirectUri: 'https://app.example.test/oauth',
        scopes: ['read'],
      },
    });
    expect(restClient.get).toHaveBeenCalledWith('/market/connect/status', {
      params: { provider: 'linear' },
    });
    expect(restClient.get).toHaveBeenCalledWith('/market/connect/connections');
    expect(restClient.get).toHaveBeenCalledWith('/market/connect/providers');
    expect(restClient.get).toHaveBeenCalledWith('/market/connect/tools', {
      params: { provider: 'linear' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/market/connect/refresh', {
      body: { provider: 'linear' },
    });
    expect(restClient.post).toHaveBeenCalledWith('/market/connect/revoke', {
      body: { provider: 'linear' },
    });
  });

  it('covers generation worker controls', async () => {
    await generationWorkerService.runTask('task-1');
    await generationWorkerService.runPending(5);

    expect(restClient.post).toHaveBeenCalledWith('/generation-workers/tasks/task-1/run');
    expect(restClient.post).toHaveBeenCalledWith('/generation-workers/run-pending', {
      params: { limit: 5 },
    });
  });

  it('covers Klavis REST tool operations', async () => {
    await klavisService.callTool({
      serverUrl: 'https://klavis.example.test/mcp',
      toolArgs: { query: 'status' },
      toolName: 'search',
    });
    await klavisService.getTools({ serverName: 'Google Calendar' });
    await klavisService.listTools({ serverUrl: 'https://klavis.example.test/mcp' });

    expect(restClient.post).toHaveBeenCalledWith('/klavis/tools/call', {
      body: {
        server_url: 'https://klavis.example.test/mcp',
        tool_args: { query: 'status' },
        tool_name: 'search',
      },
    });
    expect(restClient.get).toHaveBeenCalledWith('/klavis/tools', {
      params: { server_name: 'Google Calendar' },
    });
    expect(restClient.get).toHaveBeenCalledWith('/klavis/tools/list', {
      params: { server_url: 'https://klavis.example.test/mcp' },
    });
  });

  it('covers self-hosted cloud sandbox endpoints', async () => {
    await cloudSandboxService.callTool('runCommand', { command: 'pwd' }, { topicId: 'topic-1' });
    await cloudSandboxService.exportAndUploadFile('/tmp/out.txt', 'out.txt', 'topic-1');

    expect(restClient.post).toHaveBeenCalledWith('/cloud-sandbox/exec', {
      body: {
        params: { command: 'pwd' },
        toolName: 'runCommand',
        topicId: 'topic-1',
        userId: undefined,
      },
    });
    expect(restClient.post).toHaveBeenCalledWith('/cloud-sandbox/export-and-upload', {
      body: {
        filename: 'out.txt',
        path: '/tmp/out.txt',
        topicId: 'topic-1',
      },
    });
  });

  it('covers self-hosted business endpoints', async () => {
    await businessService.getSubscription();
    await businessService.getTopUp();
    await businessService.getSpend();

    expect(restClient.get).toHaveBeenCalledWith('/subscription');
    expect(restClient.get).toHaveBeenCalledWith('/top-up');
    expect(restClient.get).toHaveBeenCalledWith('/spend');
  });

  it('covers device gateway status and proxy', async () => {
    await deviceService.getStatus();
    await deviceService.proxy('health');
    await deviceService.proxy('/commands/run', { body: { command: 'pwd' }, method: 'POST' });

    expect(restClient.get).toHaveBeenCalledWith('/device/status');
    expect(restClient.get).toHaveBeenCalledWith('/device/proxy/health', { params: undefined });
    expect(restClient.post).toHaveBeenCalledWith('/device/proxy/commands/run', {
      body: { command: 'pwd' },
      params: undefined,
    });
  });
});
