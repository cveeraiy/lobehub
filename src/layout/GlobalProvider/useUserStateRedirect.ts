'use client';

import { useCallback } from 'react';

import { onboardingSelectors } from '@/store/user/selectors';
import { type UserInitializationState } from '@/types/user';

const redirectIfNotOn = (currentPath: string, path: string) => {
  if (!currentPath.startsWith(path)) {
    window.location.href = path;
  }
};

export const useUserStateRedirect = () =>
  useCallback((state: UserInitializationState) => {
    const { pathname } = window.location;

    if (!onboardingSelectors.needsOnboarding(state)) return;

    redirectIfNotOn(pathname, '/onboarding');
  }, []);
