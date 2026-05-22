import { restClient } from '@/libs/rest';

interface AuthStatus {
  avatarUrl?: string;
  expiresAt?: number | string;
  isAuthenticated: boolean;
  username?: string;
}

interface DeviceCodeResponse {
  deviceCode: string;
  expiresIn: number;
  interval: number;
  userCode: string;
  verificationUri: string;
}

class OAuthDeviceFlowService {
  getAuthStatus = async (providerId: string) => {
    return restClient.get<AuthStatus>('/oauth-device-flow/auth-status', {
      params: { provider_id: providerId },
    });
  };

  initiateDeviceCode = async (providerId: string) => {
    return restClient.post<DeviceCodeResponse>('/oauth-device-flow/initiate-device-code', {
      body: { providerId },
    });
  };

  pollAuthStatus = async (params: { deviceCode: string; providerId: string }) => {
    return restClient.post<{ status: string }>('/oauth-device-flow/poll-auth-status', {
      body: { deviceCode: params.deviceCode, providerId: params.providerId },
    });
  };

  revokeAuth = async (providerId: string) => {
    return restClient.post('/oauth-device-flow/revoke-auth', {
      body: { providerId },
    });
  };
}

export const oauthDeviceFlowService = new OAuthDeviceFlowService();
