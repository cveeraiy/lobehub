import { withElectronProtocolIfElectron } from '@/const/protocol';
import type {
  MarketUserInfo,
  MarketUserProfile,
  TokenResponse,
} from '@/layout/AuthProvider/MarketAuth/types';
import type { ClaimableResources } from '@/layout/AuthProvider/MarketAuth/useSocialConnect';
import { restClient } from '@/libs/rest';
import { createHeaderWithAuth } from '@/services/_auth';

interface RefreshTokenParams {
  clientId: string;
  refreshToken: string;
}

interface UpdateUserProfileParams {
  avatarUrl?: string;
  displayName: string;
  meta?: {
    bannerUrl?: string;
    description?: string;
    socialLinks?: {
      github?: string;
      twitter?: string;
      website?: string;
    };
  };
  userName: string;
}

interface ClaimResourcesParams {
  pluginIds?: string[];
  skillIds?: string[];
}

interface UpdateUserProfileResult {
  user?: Partial<MarketUserProfile>;
}

const REST_BASE = withElectronProtocolIfElectron('/api');

export class MarketAuthService {
  getUserInfo = async (token?: string): Promise<MarketUserInfo> => {
    return restClient.post('/market/oidc/userinfo', { body: { token } });
  };

  refreshToken = async ({ clientId, refreshToken }: RefreshTokenParams): Promise<TokenResponse> => {
    const body = new URLSearchParams({
      client_id: clientId,
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    });

    const res = await fetch(`${REST_BASE}/market/oidc/token`, {
      body,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(await createHeaderWithAuth()),
      },
      method: 'POST',
    });

    if (!res.ok) {
      throw new Error(`Failed to refresh market token: ${res.status} ${res.statusText}`);
    }

    return res.json();
  };

  getUserByUsername = async (username: string): Promise<MarketUserProfile> => {
    return restClient.get(`/market/user/${encodeURIComponent(username)}`);
  };

  updateUserProfile = async (params: UpdateUserProfileParams): Promise<UpdateUserProfileResult> => {
    return restClient.put('/market/user/me', { body: params });
  };

  scanClaimableResources = async (): Promise<ClaimableResources> => {
    return restClient.get('/market/social-profile/claimable-resources');
  };

  claimResources = async (params: ClaimResourcesParams) => {
    return restClient.post('/market/social-profile/claim-resources', { body: params });
  };
}

export const marketAuthService = new MarketAuthService();
