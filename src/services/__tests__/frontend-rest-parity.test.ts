import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { businessService } from '../business.rest';
import { credsService } from '../creds.rest';
import { deviceService } from '../device.rest';
import { generationWorkerService } from '../generationWorker.rest';
import { oauthDeviceFlowService } from '../oauthDeviceFlow.rest';

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
  });

  it('covers generation worker controls', async () => {
    await generationWorkerService.runTask('task-1');
    await generationWorkerService.runPending(5);

    expect(restClient.post).toHaveBeenCalledWith('/generation-workers/tasks/task-1/run');
    expect(restClient.post).toHaveBeenCalledWith('/generation-workers/run-pending', {
      params: { limit: 5 },
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
