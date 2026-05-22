import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest/client';
import type { GlobalRuntimeConfig } from '@/types/serverConfig';

import { globalService } from '../global';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest/client', () => ({
  restClient: {
    get: mockRestGet,
  },
}));

global.fetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe('GlobalRestService', () => {
  it('loads global config from the REST config endpoint', async () => {
    const mockConfig = {
      billboard: null,
      serverConfig: {
        aiProvider: {},
        disableEmailPassword: true,
        oAuthSSOProviders: ['keycloak'],
        telemetry: {},
      },
      serverFeatureFlags: {
        enableKnowledgeBase: true,
        showProvider: true,
      },
    } as GlobalRuntimeConfig;
    mockRestGet.mockResolvedValueOnce(mockConfig);

    const result = await globalService.getGlobalConfig();

    expect(result).toEqual(mockConfig);
    expect(restClient.get).toHaveBeenCalledWith('/config/global');
  });

  it('loads default agent config from the REST config endpoint', async () => {
    mockRestGet.mockResolvedValueOnce({ model: 'gpt-4o', provider: 'openai' });

    const result = await globalService.getDefaultAgentConfig();

    expect(result).toEqual({ model: 'gpt-4o', provider: 'openai' });
    expect(restClient.get).toHaveBeenCalledWith('/config/default-agent');
  });
});
