// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageModel } from '@/database/models/message';
import { SessionModel } from '@/database/models/session';
import { TopicModel } from '@/database/models/topic';
import { UserModel } from '@/database/models/user';

import { adminRouter } from '../admin';

// The serverDatabase middleware calls getServerDB() and puts it on ctx.serverDB.
// The adminAuth middleware then uses ctx.serverDB to check the caller's role.
const mockServerDB = vi.hoisted(() => {
  const _where = vi.fn().mockReturnValue(Promise.resolve([{ role: 'admin' }]));
  const _from = vi.fn().mockReturnValue({ where: _where });
  const _select = vi.fn().mockReturnValue({ from: _from });
  return { from: _from, select: _select, where: _where };
});

vi.mock('@/database/core/db-adaptor', () => ({
  getServerDB: vi.fn().mockResolvedValue(mockServerDB),
}));

vi.mock('@/database/models/message');
vi.mock('@/database/models/session');
vi.mock('@/database/models/topic');
vi.mock('@/database/models/user');
vi.mock('@/server/modules/KeyVaultsEncrypt');

describe('adminRouter', () => {
  const adminUserId = 'admin-user-id';
  const targetUserId = 'target-user-id';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getUserState', () => {
    it('should return full user state for target user', async () => {
      const mockState = {
        avatar: 'avatar.png',
        email: 'target@test.com',
        firstName: 'Test',
        fullName: 'Test User',
        interests: ['dev'],
        isOnboarded: true,
        lastName: 'User',
        onboarding: undefined,
        preference: { telemetry: true },
        settings: { general: { fontSize: 14 } },
        username: 'testuser',
      };

      vi.mocked(UserModel).mockImplementation(
        () =>
          ({
            getUserSettingsPermissions: vi
              .fn()
              .mockResolvedValue({ agentSettings: true, systemSettings: false }),
            getUserState: vi.fn().mockResolvedValue(mockState),
          }) as any,
      );

      vi.mocked(MessageModel).mockImplementation(
        () =>
          ({
            countUpTo: vi.fn().mockResolvedValue(10),
          }) as any,
      );

      vi.mocked(SessionModel).mockImplementation(
        () =>
          ({
            hasMoreThanN: vi.fn().mockResolvedValue(true),
          }) as any,
      );

      const result = await adminRouter
        .createCaller({ userId: adminUserId } as any)
        .getUserState({ userId: targetUserId });

      expect(result).toMatchObject({
        avatar: 'avatar.png',
        canEnablePWAGuide: true,
        canEnableTrace: true,
        email: 'target@test.com',
        fullName: 'Test User',
        hasConversation: true,
        isOnboard: true,
        preference: { telemetry: true },
        settings: { general: { fontSize: 14 } },
        settingsPermissions: { agentSettings: true, systemSettings: false },
        userId: targetUserId,
        username: 'testuser',
      });

      // UserModel should be instantiated with the target userId, not the admin's
      expect(UserModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
      expect(MessageModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
      expect(SessionModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
    });

    it('should handle user with no messages', async () => {
      vi.mocked(UserModel).mockImplementation(
        () =>
          ({
            getUserSettingsPermissions: vi
              .fn()
              .mockResolvedValue({ agentSettings: false, systemSettings: false }),
            getUserState: vi.fn().mockResolvedValue({
              isOnboarded: true,
              preference: {},
              settings: {},
            }),
          }) as any,
      );

      vi.mocked(MessageModel).mockImplementation(
        () =>
          ({
            countUpTo: vi.fn().mockResolvedValue(0),
          }) as any,
      );

      vi.mocked(SessionModel).mockImplementation(
        () =>
          ({
            hasMoreThanN: vi.fn().mockResolvedValue(false),
          }) as any,
      );

      const result = await adminRouter
        .createCaller({ userId: adminUserId } as any)
        .getUserState({ userId: targetUserId });

      expect(result.canEnablePWAGuide).toBe(false);
      expect(result.canEnableTrace).toBe(false);
      expect(result.hasConversation).toBe(false);
    });
  });

  describe('getUserStats', () => {
    it('should return stats for target user', async () => {
      const mockHeatmaps = [{ date: '2024-01-01', count: 5, level: 2 }];
      const mockModelRank = [{ model: 'gpt-4', count: 10 }];
      const mockSessionRank = [{ title: 'Chat 1', count: 5 }];
      const mockTopicRank = [{ title: 'Topic 1', count: 3 }];

      vi.mocked(MessageModel).mockImplementation(
        () =>
          ({
            count: vi.fn().mockResolvedValue(100),
            countWords: vi.fn().mockResolvedValue(5000),
            getHeatmaps: vi.fn().mockResolvedValue(mockHeatmaps),
            rankModels: vi.fn().mockResolvedValue(mockModelRank),
          }) as any,
      );

      vi.mocked(SessionModel).mockImplementation(
        () =>
          ({
            count: vi.fn().mockResolvedValue(10),
            rank: vi.fn().mockResolvedValue(mockSessionRank),
          }) as any,
      );

      vi.mocked(TopicModel).mockImplementation(
        () =>
          ({
            count: vi.fn().mockResolvedValue(25),
            rank: vi.fn().mockResolvedValue(mockTopicRank),
          }) as any,
      );

      const result = await adminRouter
        .createCaller({ userId: adminUserId } as any)
        .getUserStats({ userId: targetUserId });

      expect(result).toEqual({
        heatmaps: mockHeatmaps,
        messages: 100,
        modelRank: mockModelRank,
        sessionRank: mockSessionRank,
        sessions: 10,
        topicRank: mockTopicRank,
        topics: 25,
        words: 5000,
      });

      expect(MessageModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
      expect(SessionModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
      expect(TopicModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
    });
  });

  describe('getUserSettings', () => {
    it('should return settings and permissions for target user', async () => {
      const mockSettings = { general: { fontSize: 16 } };
      const mockPermissions = { agentSettings: true, systemSettings: true };

      vi.mocked(UserModel).mockImplementation(
        () =>
          ({
            getUserSettings: vi.fn().mockResolvedValue(mockSettings),
            getUserSettingsPermissions: vi.fn().mockResolvedValue(mockPermissions),
          }) as any,
      );

      const result = await adminRouter
        .createCaller({ userId: adminUserId } as any)
        .getUserSettings({ userId: targetUserId });

      expect(result).toEqual({ permissions: mockPermissions, settings: mockSettings });
      expect(UserModel).toHaveBeenCalledWith(mockServerDB, targetUserId);
    });
  });
});
