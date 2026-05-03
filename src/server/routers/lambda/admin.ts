import { z } from 'zod';

import { UserModel } from '@/database/models/user';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware/serverDatabase';

export const adminRouter = router({
  getUserSettings: authedProcedure
    .use(serverDatabase)
    .input(z.object({ userId: z.string() }))
    .query(async ({ ctx, input }) => {
      // Verify caller is admin
      if (ctx.session?.user?.role !== 'admin') {
        throw new Error('Unauthorized: Admin access required');
      }

      const userModel = new UserModel(ctx.serverDB, input.userId);
      const [settings, permissions] = await Promise.all([
        userModel.getUserSettings(),
        userModel.getUserSettingsPermissions(),
      ]);

      return { permissions, settings };
    }),

  updateUserSettings: authedProcedure
    .use(serverDatabase)
    .input(
      z.object({
        settings: z.record(z.any()),
        userId: z.string(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      if (ctx.session?.user?.role !== 'admin') {
        throw new Error('Unauthorized: Admin access required');
      }

      const userModel = new UserModel(ctx.serverDB, input.userId);

      for (const [key, value] of Object.entries(input.settings)) {
        await userModel.updateSetting(key, value);
      }

      return { success: true };
    }),

  updateUserPermissions: authedProcedure
    .use(serverDatabase)
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
      if (ctx.session?.user?.role !== 'admin') {
        throw new Error('Unauthorized: Admin access required');
      }

      const userModel = new UserModel(ctx.serverDB, input.userId);
      await userModel.updateSetting('settingsPermissions', input.permissions);

      return { success: true };
    }),
});
