import { restClient } from '@/libs/rest';

export type SocialTargetType = 'agent' | 'plugin' | 'agent-group';

export interface FollowStatus {
  isFollowing: boolean;
  isMutual: boolean;
}

export interface FollowCounts {
  followersCount: number;
  followingCount: number;
}

export interface FavoriteStatus {
  isFavorited: boolean;
}

export interface LikeStatus {
  isLiked: boolean;
}

export interface ToggleLikeResult {
  liked: boolean;
}

export interface PaginationParams {
  page?: number;
  pageSize?: number;
}

export interface PaginatedResponse<T> {
  currentPage: number;
  items: T[];
  pageSize: number;
  totalCount: number;
  totalPages: number;
}

export interface FollowUserItem {
  avatarUrl: string | null;
  displayName: string | null;
  id: number;
  namespace: string;
  userName: string | null;
}

export interface FavoriteItem {
  createdAt: string;
  id: number;
  targetId: number;
  targetType: SocialTargetType;
}

export interface FavoriteAgentItem {
  avatar: string;
  category: string;
  createdAt: string;
  description: string;
  identifier: string;
  installCount?: number;
  name: string;
  tags: string[];
}

export interface FavoritePluginItem {
  avatar: string;
  category: string;
  createdAt: string;
  description: string;
  identifier: string;
  name: string;
  tags: string[];
}

class SocialService {
  setAccessToken(_token: string | undefined) {
    // No-op: Authentication is now handled through REST auth headers
  }

  // ==================== Follow ====================

  async follow(followingId: number): Promise<void> {
    await restClient.post('/social/follow', { body: { followingId } });
  }

  async unfollow(followingId: number): Promise<void> {
    await restClient.post('/social/unfollow', { body: { followingId } });
  }

  async checkFollowStatus(userId: number): Promise<FollowStatus> {
    return restClient.get('/social/follow-status', {
      params: { targetUserId: userId } as any,
    });
  }

  async getFollowCounts(userId: number): Promise<FollowCounts> {
    return restClient.get('/social/follow-counts', { params: { userId } as any });
  }

  async getFollowing(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FollowUserItem>> {
    return restClient.get('/social/following', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }

  async getFollowers(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FollowUserItem>> {
    return restClient.get('/social/followers', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }

  // ==================== Favorite ====================

  async addFavorite(
    targetType: SocialTargetType,
    targetIdOrIdentifier: number | string,
  ): Promise<void> {
    const input =
      typeof targetIdOrIdentifier === 'string'
        ? { identifier: targetIdOrIdentifier, targetType }
        : { targetId: targetIdOrIdentifier, targetType };

    await restClient.post('/social/favorite', { body: input });
  }

  async removeFavorite(
    targetType: SocialTargetType,
    targetIdOrIdentifier: number | string,
  ): Promise<void> {
    const input =
      typeof targetIdOrIdentifier === 'string'
        ? { identifier: targetIdOrIdentifier, targetType }
        : { targetId: targetIdOrIdentifier, targetType };

    await restClient.post('/social/unfavorite', { body: input });
  }

  async checkFavoriteStatus(
    targetType: SocialTargetType,
    targetIdOrIdentifier: number | string,
  ): Promise<FavoriteStatus> {
    return restClient.get('/social/favorite-status', {
      params: { targetIdOrIdentifier, targetType } as any,
    });
  }

  async getMyFavorites(params?: PaginationParams): Promise<PaginatedResponse<FavoriteItem>> {
    return restClient.get('/social/my-favorites', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
      } as any,
    });
  }

  async getUserFavoriteAgents(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FavoriteAgentItem>> {
    return restClient.get('/social/favorite-agents', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }

  async getUserFavoritePlugins(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FavoritePluginItem>> {
    return restClient.get('/social/favorite-plugins', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }

  // ==================== Like ====================

  async like(targetType: SocialTargetType, targetIdOrIdentifier: number | string): Promise<void> {
    const input =
      typeof targetIdOrIdentifier === 'string'
        ? { identifier: targetIdOrIdentifier, targetType }
        : { targetId: targetIdOrIdentifier, targetType };

    await restClient.post('/social/like', { body: input });
  }

  async unlike(targetType: SocialTargetType, targetIdOrIdentifier: number | string): Promise<void> {
    const input =
      typeof targetIdOrIdentifier === 'string'
        ? { identifier: targetIdOrIdentifier, targetType }
        : { targetId: targetIdOrIdentifier, targetType };

    await restClient.post('/social/unlike', { body: input });
  }

  async checkLikeStatus(
    targetType: SocialTargetType,
    targetIdOrIdentifier: number | string,
  ): Promise<LikeStatus> {
    return restClient.get('/social/like-status', {
      params: { targetIdOrIdentifier, targetType } as any,
    });
  }

  async toggleLike(
    targetType: SocialTargetType,
    targetIdOrIdentifier: number | string,
  ): Promise<ToggleLikeResult> {
    const input =
      typeof targetIdOrIdentifier === 'string'
        ? { identifier: targetIdOrIdentifier, targetType }
        : { targetId: targetIdOrIdentifier, targetType };

    return restClient.post('/social/toggle-like', { body: input });
  }

  async getUserLikedAgents(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FavoriteAgentItem>> {
    return restClient.get('/social/liked-agents', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }

  async getUserLikedPlugins(
    userId: number,
    params?: PaginationParams,
  ): Promise<PaginatedResponse<FavoritePluginItem>> {
    return restClient.get('/social/liked-plugins', {
      params: {
        limit: params?.pageSize,
        offset: params?.page ? (params.page - 1) * (params.pageSize || 10) : undefined,
        userId,
      } as any,
    });
  }
}

export const socialService = new SocialService();
