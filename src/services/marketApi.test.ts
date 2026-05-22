import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { marketApiService } from './marketApi';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/services/discover', () => ({
  discoverService: {
    safeInjectMPToken: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('MarketApiService REST', () => {
  it('maps publish agent payloads to Python REST body shape', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({
      identifier: 'agent-one',
      isNewAgent: true,
      success: true,
    });

    await marketApiService.publishOrCreateAgent({
      editorData: { tools: [] },
      identifier: 'agent-one',
      name: 'Agent One',
      tokenUsage: 5,
    });

    expect(restClient.post).toHaveBeenCalledWith('/market/agent/publish-or-create', {
      body: {
        editorData: { tools: [] },
        editor_data: { tools: [] },
        identifier: 'agent-one',
        name: 'Agent One',
        tokenUsage: 5,
        token_usage: 5,
      },
    });
  });

  it('maps feedback payloads to Python REST body shape', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({ success: true });

    await marketApiService.submitFeedback({
      clientInfo: { userAgent: 'ua' },
      message: 'Body',
      screenshotUrl: 's3://shot',
      title: 'Bug',
    });

    expect(restClient.post).toHaveBeenCalledWith('/market/feedback', {
      body: {
        client_info: {
          language: undefined,
          timezone: undefined,
          url: undefined,
          user_agent: 'ua',
        },
        email: undefined,
        message: 'Body',
        screenshot_url: 's3://shot',
        title: 'Bug',
      },
    });
  });

  it('searches skills through the REST market endpoint', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      currentPage: 1,
      items: [],
      pageSize: 20,
      totalCount: 0,
    });

    await marketApiService.searchSkill({ page: 1, pageSize: 20, q: 'slack' });

    expect(restClient.get).toHaveBeenCalledWith('/market/skill/list', {
      params: { page: 1, pageSize: 20, q: 'slack' },
    });
  });
});
