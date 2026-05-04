'use client';

import { type UserInitializationState } from '@lobechat/types';
import {
  createContext,
  type ReactNode,
  use,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import { DEFAULT_PREFERENCE } from '@/const/user';
import { lambdaClient } from '@/libs/trpc/client';
import { type UserStore, useUserStore } from '@/store/user';
import { type LobeUser } from '@/types/user';

export interface AdminViewContextValue {
  isAdminView: true;
  isLoading: boolean;
  readOnly: boolean;
  targetUserId: string;
  targetUserState: UserInitializationState | null;
  targetUserStats: AdminUserStats | null;
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

const AdminViewContext = createContext<AdminViewContextValue | null>(null);

export const useAdminViewContext = (): AdminViewContextValue | null => {
  return use(AdminViewContext);
};

export const useIsAdminView = (): boolean => {
  const ctx = use(AdminViewContext);
  return ctx?.isAdminView ?? false;
};

type SnapshotKeys =
  | 'defaultSettings'
  | 'isUserStateInit'
  | 'preference'
  | 'resetSettings'
  | 'setSettings'
  | 'settings'
  | 'settingsPermissions'
  | 'updateAvatar'
  | 'updateFullName'
  | 'updateInterests'
  | 'updateUsername'
  | 'user';

type StoreSnapshot = Pick<UserStore, SnapshotKeys>;

const takeSnapshot = (): StoreSnapshot => {
  const s = useUserStore.getState();
  return {
    defaultSettings: s.defaultSettings,
    isUserStateInit: s.isUserStateInit,
    preference: s.preference,
    resetSettings: s.resetSettings,
    setSettings: s.setSettings,
    settings: s.settings,
    settingsPermissions: s.settingsPermissions,
    updateAvatar: s.updateAvatar,
    updateFullName: s.updateFullName,
    updateInterests: s.updateInterests,
    updateUsername: s.updateUsername,
    user: s.user,
  };
};

const hydrateStore = (data: UserInitializationState) => {
  const isEmpty = Object.keys(data.preference || {}).length === 0;
  const preference = isEmpty ? DEFAULT_PREFERENCE : data.preference;

  const user: LobeUser = {
    avatar: data.avatar,
    email: data.email,
    firstName: data.firstName,
    fullName: data.fullName,
    id: data.userId,
    interests: data.interests,
    username: data.username,
  };

  // No-op to prevent writes in read-only admin view
  const noop = async () => {};

  useUserStore.setState({
    isUserStateInit: true,
    preference,
    // Override mutations with no-ops to prevent writes in read-only mode
    resetSettings: noop,
    setSettings: noop,
    settings: data.settings || {},
    settingsPermissions: data.settingsPermissions ?? {
      agentSettings: false,
      systemSettings: false,
    },
    updateAvatar: noop,
    updateFullName: noop,
    updateInterests: noop,
    updateUsername: noop,
    user,
  });
};

const restoreSnapshot = (snapshot: StoreSnapshot) => {
  useUserStore.setState(snapshot);
};

interface AdminViewProviderProps {
  children: ReactNode;
  targetUserId: string;
}

export const AdminViewProvider = ({ children, targetUserId }: AdminViewProviderProps) => {
  const [targetUserState, setTargetUserState] = useState<UserInitializationState | null>(null);
  const [targetUserStats, setTargetUserStats] = useState<AdminUserStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const snapshotRef = useRef<StoreSnapshot | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [state, stats] = await Promise.all([
        lambdaClient.admin.getUserState.query({ userId: targetUserId }),
        lambdaClient.admin.getUserStats.query({ userId: targetUserId }),
      ]);
      setTargetUserState(state);
      setTargetUserStats(stats);

      // Snapshot current admin's store state before hydrating
      snapshotRef.current = takeSnapshot();
      hydrateStore(state);
    } catch (error) {
      console.error('[AdminViewProvider] Failed to fetch admin view data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [targetUserId]);

  useEffect(() => {
    fetchData();

    // Restore admin's own store state on unmount
    return () => {
      if (snapshotRef.current) {
        restoreSnapshot(snapshotRef.current);
      }
    };
  }, [fetchData]);

  const value: AdminViewContextValue = {
    isAdminView: true,
    isLoading,
    readOnly: true,
    targetUserId,
    targetUserState,
    targetUserStats,
  };

  return <AdminViewContext value={value}>{children}</AdminViewContext>;
};

export default AdminViewContext;
