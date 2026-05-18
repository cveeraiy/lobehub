import { lambdaClient } from '@/libs/trpc/client';
import { shouldUseRest } from '@/services/_restFlag';

import type { AdminUserSettingsResult, AdminUserStats } from './admin.rest';
import { adminService as restService } from './admin.rest';

const trpcService = {
  getUserSettings: (userId: string): Promise<AdminUserSettingsResult> =>
    lambdaClient.admin.getUserSettings.query({ userId }),
  getUserState: (userId: string) => lambdaClient.admin.getUserState.query({ userId }),
  getUserStats: (userId: string): Promise<AdminUserStats> =>
    lambdaClient.admin.getUserStats.query({ userId }),
  updateUserPermissions: (
    userId: string,
    permissions: { agentSettings: boolean; systemSettings: boolean },
  ) => lambdaClient.admin.updateUserPermissions.mutate({ permissions, userId }),
};

export const adminService = shouldUseRest('admin') ? restService : trpcService;
