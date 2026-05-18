import { restClient } from '@/libs/rest';

class OAuthDeviceFlowService {
  getAuthStatus = async (providerId: string) => {
    return restClient.get<{
      avatarUrl?: string;
      expiresAt?: string;
      isAuthenticated: boolean;
      username?: string;
    }>('/ai-infra/oauth-device-flow/status', { params: { provider_id: providerId } });
  };

  initiateDeviceCode = async (providerId: string) => {
    return restClient.post<{
      deviceCode: string;
      expiresIn: number;
      interval: number;
      userCode: string;
      verificationUri: string;
    }>('/ai-infra/oauth-device-flow/device-code', { body: { provider_id: providerId } });
  };

  pollAuthStatus = async (params: { deviceCode: string; providerId: string }) => {
    return restClient.post<{ status: string }>('/ai-infra/oauth-device-flow/poll', {
      body: { device_code: params.deviceCode, provider_id: params.providerId },
    });
  };

  revokeAuth = async (providerId: string) => {
    return restClient.post('/ai-infra/oauth-device-flow/revoke', {
      body: { provider_id: providerId },
    });
  };
}

export const oauthDeviceFlowService = new OAuthDeviceFlowService();
