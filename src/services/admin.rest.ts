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

class AdminService {
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
