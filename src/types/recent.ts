import type { ChatTopicMetadata } from '@/types/topic';

export interface RecentItem {
  agentId?: string | null;
  icon: string;
  id: string;
  metadata?: ChatTopicMetadata;
  routePath: string;
  title: string;
  type: 'document' | 'task' | 'topic';
  updatedAt: Date;
}
