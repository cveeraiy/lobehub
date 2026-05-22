import type { UserInitializationState } from '@lobechat/types';

import { restClient } from '@/libs/rest';

interface SettingsPermissions {
  agentSettings: boolean;
  systemSettings: boolean;
}

export interface AdminUserSettingsResult {
  permissions?: SettingsPermissions;
  settings?: Record<string, any>;
}

export interface AdminUserStats {
  heatmaps: any;
  messages: number;
  modelRank: any[];
  sessionRank: any[];
  sessions: number;
  topicRank: any[];
  topics: number;
  words: number;
}

export interface AdminUserListItem {
  accessedAt?: string | null;
  createdAt?: string | null;
  email?: string | null;
  firstName?: string | null;
  fullName?: string | null;
  id: string;
  isOnboarded?: boolean;
  orgId?: string | null;
  orgRole?: string | null;
  orgSlug?: string | null;
  username?: string | null;
}

interface RestAdminUserListItem {
  accessed_at?: string | null;
  created_at?: string | null;
  email?: string | null;
  first_name?: string | null;
  full_name?: string | null;
  id: string;
  is_onboarded?: boolean;
  org_id?: string | null;
  org_role?: string | null;
  org_slug?: string | null;
  username?: string | null;
}

const normalizeUser = (user: RestAdminUserListItem): AdminUserListItem => ({
  accessedAt: user.accessed_at,
  createdAt: user.created_at,
  email: user.email,
  firstName: user.first_name,
  fullName: user.full_name,
  id: user.id,
  isOnboarded: user.is_onboarded,
  orgId: user.org_id,
  orgRole: user.org_role,
  orgSlug: user.org_slug,
  username: user.username,
});

class AdminService {
  listUsers = async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<AdminUserListItem[]> => {
    const users = await restClient.get<RestAdminUserListItem[]>('/admin/users', {
      params: {
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
      },
    });

    return users.map(normalizeUser);
  };

  getUserSettings = async (userId: string): Promise<AdminUserSettingsResult> => {
    return restClient.get(`/admin/users/${userId}/settings`);
  };

  getUserState = async (userId: string): Promise<UserInitializationState> => {
    return restClient.get(`/admin/users/${userId}/state`);
  };

  getUserStats = async (userId: string): Promise<AdminUserStats> => {
    return restClient.get(`/admin/users/${userId}/stats`);
  };

  updateUserPermissions = async (userId: string, permissions: SettingsPermissions) => {
    return restClient.put(`/admin/users/${userId}/permissions`, {
      body: { permissions },
    });
  };
}

export const adminService = new AdminService();
