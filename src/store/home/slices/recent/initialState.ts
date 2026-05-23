import type { RecentItem } from '@/types/recent';

export interface RecentState {
  allRecentsDrawerOpen: boolean;
  isRecentsInit: boolean;
  recents: RecentItem[];
}

export const initialRecentState: RecentState = {
  allRecentsDrawerOpen: false,
  isRecentsInit: false,
  recents: [],
};
