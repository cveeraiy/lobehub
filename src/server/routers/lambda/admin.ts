import { TRPCError } from '@trpc/server';
import { eq } from 'drizzle-orm';
import { z } from 'zod';

import { UserModel } from '@/database/models/user';
import { users } from '@/database/schemas';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { trpc } from '@/libs/trpc/lambda/init';
import { serverDatabase } from '@/libs/trpc/lambda/middleware/serverDatabase';

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
