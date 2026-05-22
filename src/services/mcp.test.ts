import { type ChatToolPayload } from '@lobechat/types';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { mcpService } from './mcp';

vi.mock('@lobechat/const', () => ({
  CURRENT_VERSION: '1.0.0',
}));

vi.mock('@lobechat/utils', () => ({
  safeParseJSON: vi.fn((value: string) => {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }),
}));

vi.mock('@/libs/rest', () => ({
  restClient: {
    post: vi.fn(),
  },
}));

vi.mock('./discover', () => ({
  discoverService: {
    reportPluginCall: vi.fn().mockResolvedValue(undefined),
    safeInjectMPToken: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockGetToolStoreState = vi.fn();
const mockPluginSelectors = {
  getCustomPluginById: vi.fn(),
  getInstalledPluginById: vi.fn(),
};

vi.mock('@/store/tool/store', () => ({
  getToolStoreState: () => mockGetToolStoreState(),
}));

vi.mock('@/store/tool/selectors', () => ({
  pluginSelectors: mockPluginSelectors,
}));

describe('MCPService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetToolStoreState.mockReturnValue({});
  });

  it('invokes installed MCP tools through the REST endpoint', async () => {
    const plugin = {
      customParams: {
        mcp: {
          env: { API_KEY: 'test-key' },
          name: 'test-plugin',
          type: 'sse',
        },
      },
      manifest: {
        meta: { avatar: 'T', description: 'Test plugin', title: 'Test Plugin' },
        version: '1.0.0',
      },
      settings: { timeout: 5000 },
    };
    mockPluginSelectors.getInstalledPluginById.mockReturnValue(() => plugin);
    mockPluginSelectors.getCustomPluginById.mockReturnValue(() => null);
    vi.mocked(restClient.post).mockResolvedValueOnce({ content: 'ok', state: {}, success: true });

    const payload: ChatToolPayload = {
      apiName: 'search',
      arguments: '{"query":"rest"}',
      id: 'tool-call-1',
      identifier: 'test-plugin',
      type: 'mcp',
    };

    await expect(mcpService.invokeMcpToolCall(payload, { topicId: 'topic-1' })).resolves.toEqual({
      content: 'ok',
      state: {},
      success: true,
    });
    expect(restClient.post).toHaveBeenCalledWith('/mcp/tools/call', {
      body: expect.objectContaining({
        args: '{"query":"rest"}',
        toolName: 'search',
      }),
      signal: undefined,
    });
  });

  it('invokes cloud MCP tools through the REST endpoint with api params', async () => {
    const plugin = {
      customParams: { mcp: { type: 'cloud' } },
      manifest: {
        meta: { avatar: 'C', description: 'Cloud plugin', title: 'Cloud Plugin' },
        version: '1.0.0',
      },
    };
    mockPluginSelectors.getInstalledPluginById.mockReturnValue(() => plugin);
    mockPluginSelectors.getCustomPluginById.mockReturnValue(() => null);
    vi.mocked(restClient.post).mockResolvedValueOnce({ content: 'ok', state: {}, success: true });

    await mcpService.invokeMcpToolCall(
      {
        apiName: 'lookup',
        arguments: '{"id":"123"}',
        id: 'tool-call-1',
        identifier: 'cloud-plugin',
        type: 'mcp',
      },
      { topicId: 'topic-1' },
    );

    expect(restClient.post).toHaveBeenCalledWith('/mcp/tools/call', {
      body: expect.objectContaining({
        apiParams: { id: '123' },
        identifier: 'cloud-plugin',
        toolName: 'lookup',
      }),
      signal: undefined,
    });
  });

  it('returns undefined when no plugin is installed', async () => {
    mockPluginSelectors.getInstalledPluginById.mockReturnValue(() => null);
    mockPluginSelectors.getCustomPluginById.mockReturnValue(() => null);

    await expect(
      mcpService.invokeMcpToolCall(
        {
          apiName: 'missing',
          arguments: '{}',
          id: 'tool-call-1',
          identifier: 'missing-plugin',
          type: 'mcp',
        },
        {},
      ),
    ).resolves.toBeUndefined();
    expect(restClient.post).not.toHaveBeenCalled();
  });

  it('loads streamable manifests through REST', async () => {
    const manifest = { api: [], identifier: 'remote', meta: { title: 'Remote' }, type: 'default' };
    vi.mocked(restClient.post).mockResolvedValueOnce(manifest);

    await expect(
      mcpService.getStreamableMcpServerManifest({
        auth: { token: 'token', type: 'bearer' },
        headers: { 'x-test': '1' },
        identifier: 'remote',
        metadata: { avatar: 'R', description: 'Remote', name: 'Remote' },
        url: 'https://mcp.example.test',
      }),
    ).resolves.toEqual(manifest);
    expect(restClient.post).toHaveBeenCalledWith('/mcp/manifest/http', {
      body: {
        auth: { token: 'token', type: 'bearer' },
        headers: { 'x-test': '1' },
        identifier: 'remote',
        metadata: { avatar: 'R', description: 'Remote', name: 'Remote' },
        url: 'https://mcp.example.test',
      },
      signal: undefined,
    });
  });

  it('reports web-only stdio and installation limitations', async () => {
    await expect(
      mcpService.getStdioMcpServerManifest({ command: 'node', name: 'stdio' }),
    ).rejects.toThrow('stdio MCP servers are not supported in web builds');
    await expect(mcpService.checkInstallation({} as any)).resolves.toEqual({
      installable: false,
      missing: [],
    });
  });
});
