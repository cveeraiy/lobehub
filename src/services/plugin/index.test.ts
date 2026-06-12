import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { pluginService } from './index';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('PluginService REST', () => {
  it('maps customParams to Python REST body shape when installing', async () => {
    await pluginService.installPlugin({
      customParams: { endpoint: 'https://example.com' },
      identifier: 'plugin-a',
      manifest: { identifier: 'plugin-a', meta: { title: 'Plugin A' } } as any,
      settings: { enabled: true },
      type: 'customPlugin',
    });

    expect(restClient.post).toHaveBeenCalledWith('/plugins', {
      body: expect.objectContaining({
        custom_params: { endpoint: 'https://example.com' },
        identifier: 'plugin-a',
        type: 'customPlugin',
      }),
    });
  });

  it('normalizes custom_params from Python list responses', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce([
      {
        custom_params: { endpoint: 'https://example.com' },
        identifier: 'plugin-a',
        manifest: {},
        type: 'customPlugin',
      },
    ]);

    const result = await pluginService.getInstalledPlugins();

    expect(restClient.get).toHaveBeenCalledWith('/plugins');
    expect(result[0]).toMatchObject({
      customParams: { endpoint: 'https://example.com' },
      identifier: 'plugin-a',
    });
  });

  it('maps updates to Python REST body shape', async () => {
    await pluginService.updatePlugin('plugin-a', {
      customParams: { manifestUrl: 'https://example.com/manifest.json' },
      settings: { enabled: true },
    });

    expect(restClient.put).toHaveBeenCalledWith('/plugins/plugin-a', {
      body: {
        custom_params: { manifestUrl: 'https://example.com/manifest.json' },
        manifest: undefined,
        settings: { enabled: true },
      },
    });
  });
});
