import { type UserInitializationState, type UserPreference } from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import { eq } from 'drizzle-orm';
import { z } from 'zod';

import { MessageModel } from '@/database/models/message';
import { SessionModel } from '@/database/models/session';
import { TopicModel } from '@/database/models/topic';
import { UserModel } from '@/database/models/user';
import { users } from '@/database/schemas';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { trpc } from '@/libs/trpc/lambda/init';
import { serverDatabase } from '@/libs/trpc/lambda/middleware/serverDatabase';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';

const adminAuth = trpc.middleware(async ({ ctx, next }) => {
  const { serverDB, userId } = ctx as any;
  if (!serverDB || !userId) {
    throw new TRPCError({ code: 'UNAUTHORIZED', message: 'Not authenticated' });
  }
  const row = await serverDB
    .select({ role: users.role })
    .from(users)
    .where(eq(users.id, userId))
    .then((r: any[]) => r[0]);

  if (row?.role !== 'admin') {
    throw new TRPCError({ code: 'FORBIDDEN', message: 'Admin access required' });
  }
  return next();
});

const adminProcedure = authedProcedure.use(serverDatabase).use(adminAuth);

export const adminRouter = router({
  getUserState: adminProcedure
    .input(z.object({ userId: z.string() }))
    .query(async ({ ctx, input }): Promise<UserInitializationState> => {
      const userModel = new UserModel(ctx.serverDB, input.userId);
      const messageModel = new MessageModel(ctx.serverDB, input.userId);
      const sessionModel = new SessionModel(ctx.serverDB, input.userId);

      const [state, messageCount, hasExtraSession, settingsPermissions] = await Promise.all([
        userModel.getUserState(KeyVaultsGateKeeper.getUserKeyVaults),
        messageModel.countUpTo(5),
        sessionModel.hasMoreThanN(1),
        userModel.getUserSettingsPermissions(),
      ]);

      const hasMoreThan4Messages = messageCount > 4;
      const hasAnyMessages = messageCount > 0;

      return {
        avatar: state.avatar,
        canEnablePWAGuide: hasMoreThan4Messages,
        canEnableTrace: hasMoreThan4Messages,
        email: state.email,
        firstName: state.firstName,
        fullName: state.fullName,
        hasConversation: hasAnyMessages || hasExtraSession,
        agentOnboarding: state.agentOnboarding,
        interests: state.interests,
        isOnboard: state.isOnboarded ?? true,
        lastName: state.lastName,
        onboarding: state.onboarding,
        preference: state.preference as UserPreference,
        settingsPermissions,
        settings: state.settings,
        userId: input.userId,
        username: state.username,
      };
    }),

  getUserStats: adminProcedure
    .input(z.object({ userId: z.string() }))
    .query(async ({ ctx, input }) => {
      const messageModel = new MessageModel(ctx.serverDB, input.userId);
      const sessionModel = new SessionModel(ctx.serverDB, input.userId);
      const topicModel = new TopicModel(ctx.serverDB, input.userId);

      const [messages, sessions, topics, words, heatmaps, modelRank, sessionRank, topicRank] =
        await Promise.all([
          messageModel.count(),
          sessionModel.count(),
          topicModel.count(),
          messageModel.countWords(),
          messageModel.getHeatmaps(),
          messageModel.rankModels(),
          sessionModel.rank(),
          topicModel.rank(),
        ]);

      return {
        heatmaps,
        messages,
        modelRank,
        sessionRank,
        sessions,
        topicRank,
        topics,
        words,
      };
    }),

  getUserSettings: adminProcedure
    .input(z.object({ userId: z.string() }))
    .query(async ({ ctx, input }) => {
      const userModel = new UserModel(ctx.serverDB, input.userId);
      const [settings, permissions] = await Promise.all([
        userModel.getUserSettings(),
        userModel.getUserSettingsPermissions(),
      ]);

      return { permissions, settings };
    }),

  updateUserSettings: adminProcedure
    .input(
      z.object({
        settings: z.record(z.any()),
        userId: z.string(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const userModel = new UserModel(ctx.serverDB, input.userId);

      for (const [key, value] of Object.entries(input.settings)) {
        await userModel.updateSetting(key, value);
      }

      return { success: true };
    }),

  updateUserPermissions: adminProcedure
    .input(
      z.object({
        permissions: z.object({
          agentSettings: z.boolean(),
          systemSettings: z.boolean(),
        }),
        userId: z.string(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const userModel = new UserModel(ctx.serverDB, input.userId);
      await userModel.updateSetting('settingsPermissions', input.permissions);

      return { success: true };
    }),
});
