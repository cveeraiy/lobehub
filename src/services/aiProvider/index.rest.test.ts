import { beforeEach, describe, expect, it, vi } from 'vitest';

import { aiProviderService } from './index.rest';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AiProviderService REST', () => {
  it('normalizes runtime state model fields from Python snake_case', async () => {
    mockRestGet.mockResolvedValueOnce({
      enabledAiModels: [
        {
          abilities: { vision: true },
          context_window_tokens: 200_000,
          display_name: 'Claude Sonnet',
          enabled: true,
          id: 'global.anthropic.claude-sonnet-4-6',
          provider_id: 'bedrock',
          released_at: '2026-02-17',
          type: 'chat',
        },
      ],
      enabledAiProviders: [{ id: 'bedrock', name: 'AWS Bedrock', source: 'builtin' }],
      enabledChatAiProviders: [{ id: 'bedrock', name: 'AWS Bedrock', source: 'builtin' }],
      runtimeConfig: {
        bedrock: {
          fetch_on_client: false,
          key_vaults: { region: 'us-east-1' },
          settings: { sdkType: 'bedrock' },
        },
      },
    });

    const result = await aiProviderService.getAiProviderRuntimeState();

    expect(mockRestGet).toHaveBeenCalledWith('/ai-infra/providers/runtime-state', {
      params: undefined,
    });
    expect(result.enabledAiModels[0]).toMatchObject({
      contextWindowTokens: 200_000,
      displayName: 'Claude Sonnet',
      providerId: 'bedrock',
      releasedAt: '2026-02-17',
    });
    expect(result.runtimeConfig.bedrock).toMatchObject({
      fetchOnClient: false,
      keyVaults: { region: 'us-east-1' },
      settings: { sdkType: 'bedrock' },
    });
  });
});
