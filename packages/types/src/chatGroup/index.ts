import type { LobeChatGroupConfig } from '../agentGroup';

export type { LobeChatGroupChatConfig, LobeChatGroupConfig } from '../agentGroup';
export { ChatGroupConfigSchema, InsertChatGroupSchema } from '../agentGroup';

export interface ChatGroupItem {
  accessedAt?: Date | string | null;
  avatar?: string | null;
  backgroundColor?: string | null;
  clientId?: string | null;
  config?: LobeChatGroupConfig | null;
  content?: string | null;
  createdAt: Date | string;
  description?: string | null;
  editorData?: Record<string, unknown> | null;
  groupId?: string | null;
  id: string;
  marketIdentifier?: string | null;
  pinned?: boolean | null;
  title?: string | null;
  updatedAt: Date | string;
  userId: string;
}

export type NewChatGroup = Partial<ChatGroupItem> & Pick<ChatGroupItem, 'userId'>;

export interface ChatGroupAgentItem {
  accessedAt?: Date | string | null;
  agentId: string;
  chatGroupId: string;
  createdAt: Date | string;
  enabled?: boolean | null;
  order?: number | null;
  role?: string | null;
  updatedAt: Date | string;
  userId: string;
}

export type NewChatGroupAgent = Partial<ChatGroupAgentItem> &
  Pick<ChatGroupAgentItem, 'agentId' | 'chatGroupId' | 'userId'>;
