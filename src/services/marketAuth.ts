import type {
  MarketUserInfo,
  MarketUserProfile,
  TokenResponse,
} from '@/layout/AuthProvider/MarketAuth/types';
import type { ClaimableResources } from '@/layout/AuthProvider/MarketAuth/useSocialConnect';
import { lambdaClient } from '@/libs/trpc/client';

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

export class MarketAuthService {
  getUserInfo = async (token?: string): Promise<MarketUserInfo> => {
    return lambdaClient.market.oidc.getUserInfo.mutate({ token }) as Promise<MarketUserInfo>;
  };

  refreshToken = async (params: RefreshTokenParams): Promise<TokenResponse> => {
    return lambdaClient.market.oidc.refreshToken.mutate(params) as Promise<TokenResponse>;
  };

  getUserByUsername = async (username: string): Promise<MarketUserProfile> => {
    return lambdaClient.market.user.getUserByUsername.query({
      username,
    }) as Promise<MarketUserProfile>;
  };

  updateUserProfile = async (params: UpdateUserProfileParams): Promise<UpdateUserProfileResult> => {
    return lambdaClient.market.user.updateUserProfile.mutate(
      params,
    ) as Promise<UpdateUserProfileResult>;
  };

  scanClaimableResources = async (): Promise<ClaimableResources> => {
    return lambdaClient.market.socialProfile.scanClaimableResources.query();
  };

  claimResources = async (params: ClaimResourcesParams) => {
    return lambdaClient.market.socialProfile.claimResources.mutate(params);
  };
}

export const marketAuthService = new MarketAuthService();
