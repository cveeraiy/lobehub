import { useCallback } from 'react';

interface PopupScope {
  agentId?: string;
  groupId?: string;
}

interface ScopeQuery {
  agentId?: string;
  groupId?: string;
  topicId: string;
}

// Desktop popup registry removed for enterprise web-only build.
// All hooks return empty/no-op values.

export const useTopicPopupsRegistry = () => [] as never[];

export const useTopicInPopup = (_scope: ScopeQuery) => undefined;

export const useFocusTopicPopup = (_scope: PopupScope) => {
  return useCallback(async (_topicId?: string) => false, []);
};
