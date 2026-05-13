'use client';

import { useMemo } from 'react';

import { type ActionsBarConfig } from '@/features/Conversation/types';
import { useUserStore } from '@/store/user';
import { userGeneralSettingsSelectors } from '@/store/user/selectors';

export const useActionsBarConfig = (): ActionsBarConfig => {
  const isDevMode = useUserStore((s) => userGeneralSettingsSelectors.config(s).isDevMode);

  return useMemo<ActionsBarConfig>(() => {
    // Dev mode adds `branching` to the default bars. Everything else falls
    // back to each role's component-level defaults.
    if (isDevMode) {
      return {
        assistant: { bar: ['edit', 'copy', 'branching'] },
        user: { bar: ['regenerate', 'edit', 'copy', 'branching'] },
      };
    }

    return {};
  }, [isDevMode]);
};
