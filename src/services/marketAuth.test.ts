import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import { createHeaderWithAuth } from '@/services/_auth';

import { marketAuthService } from './marketAuth';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('@/services/_auth', () => ({
  createHeaderWithAuth: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  vi.mocked(createHeaderWithAuth).mockResolvedValue({ 'x-test-auth': 'yes' });
});

describe('MarketAuthService REST', () => {
  it('uses REST userinfo endpoint with optional token', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({ accountId: 1 });

    await marketAuthService.getUserInfo('market-token');

    expect(restClient.post).toHaveBeenCalledWith('/market/oidc/userinfo', {
      body: { token: 'market-token' },
    });
  });

  it('posts refresh-token requests as form data', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({ accessToken: 'new-token' }),
      ok: true,
    });
    vi.stubGlobal('fetch', fetchMock);

    await marketAuthService.refreshToken({
      clientId: 'lobechat-com',
      refreshToken: 'old-refresh-token',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/market/oidc/token',
      expect.objectContaining({
        credentials: 'include',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'x-test-auth': 'yes',
        },
        method: 'POST',
      }),
    );
    const body = fetchMock.mock.calls[0][1].body as URLSearchParams;
    expect(body.get('client_id')).toBe('lobechat-com');
    expect(body.get('grant_type')).toBe('refresh_token');
    expect(body.get('refresh_token')).toBe('old-refresh-token');
  });

  it('encodes usernames and uses REST profile endpoints', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({ id: 1 });
    vi.mocked(restClient.put).mockResolvedValueOnce({ user: { id: 1 } });

    await marketAuthService.getUserByUsername('market user');
    await marketAuthService.updateUserProfile({
      displayName: 'Market User',
      userName: 'market-user',
    });

    expect(restClient.get).toHaveBeenCalledWith('/market/user/market%20user');
    expect(restClient.put).toHaveBeenCalledWith('/market/user/me', {
      body: {
        displayName: 'Market User',
        userName: 'market-user',
      },
    });
  });

  it('uses REST claim endpoints', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({ plugins: [], skills: [] });
    vi.mocked(restClient.post).mockResolvedValueOnce({ success: true });

    await marketAuthService.scanClaimableResources();
    await marketAuthService.claimResources({ pluginIds: ['2'], skillIds: ['1'] });

    expect(restClient.get).toHaveBeenCalledWith('/market/social-profile/claimable-resources');
    expect(restClient.post).toHaveBeenCalledWith('/market/social-profile/claim-resources', {
      body: { pluginIds: ['2'], skillIds: ['1'] },
    });
  });
});
