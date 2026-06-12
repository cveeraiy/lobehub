import type { CompressionGroupMetadata, MessageGroupItem } from '@lobechat/types';
import { MessageGroupType } from '@lobechat/types';
import { and, eq, inArray, isNull } from 'drizzle-orm';

import { messageGroups, messages } from '@/database/schemas';
import type { LobeChatDatabase } from '@/server/types/database';

export interface CreateCompressionGroupParams {
  content: string;
  editorData?: any;
  messageIds: string[];
  metadata: CompressionGroupMetadata;
  topicId: string;
}

export interface CompressionGroupResult {
  content: string | null;
  createdAt: Date;
  description: string | null;
  editorData: unknown;
  id: string;
  metadata: CompressionGroupMetadata | null;
  topicId: string | null;
  type: string | null;
}

export class CompressionRepository {
  private userId: string;
  private db: LobeChatDatabase;

  constructor(db: LobeChatDatabase, userId: string) {
    this.userId = userId;
    this.db = db;
  }

  async createCompressionGroup(params: CreateCompressionGroupParams): Promise<string> {
    const { topicId, content, editorData, messageIds, metadata } = params;

    const result = (await this.db
      .insert(messageGroups)
      .values({
        content,
        description: JSON.stringify(metadata),
        editorData,
        topicId,
        type: MessageGroupType.Compression,
        userId: this.userId,
      })
      .returning()) as MessageGroupItem[];

    const group = result[0];

    if (messageIds.length > 0) {
      await this.markMessagesAsCompressed(messageIds, group.id);
    }

    return group.id;
  }

  async getCompressionGroups(topicId: string): Promise<CompressionGroupResult[]> {
    const groups = await this.db
      .select()
      .from(messageGroups)
      .where(
        and(
          eq(messageGroups.userId, this.userId),
          eq(messageGroups.topicId, topicId),
          eq(messageGroups.type, MessageGroupType.Compression),
        ),
      )
      .orderBy(messageGroups.createdAt);

    return groups.map((group: any) => ({
      ...group,
      metadata: group.description ? JSON.parse(group.description) : null,
    })) as unknown as CompressionGroupResult[];
  }

  async getLatestCompressionGroup(topicId: string): Promise<CompressionGroupResult | null> {
    const groups = await this.getCompressionGroups(topicId);
    return groups.length > 0 ? groups.at(-1)! : null;
  }

  async updateCompressionContent(
    groupId: string,
    content: string,
    metadata?: Partial<CompressionGroupMetadata>,
  ): Promise<void> {
    const updateData: Record<string, unknown> = {
      content,
      updatedAt: new Date(),
    };

    if (metadata) {
      const existing = await this.db
        .select({ description: messageGroups.description })
        .from(messageGroups)
        .where(and(eq(messageGroups.id, groupId), eq(messageGroups.userId, this.userId)));

      const existingMetadata = existing[0]?.description ? JSON.parse(existing[0].description) : {};
      updateData.description = JSON.stringify({ ...existingMetadata, ...metadata });
    }

    await this.db
      .update(messageGroups)
      .set(updateData)
      .where(and(eq(messageGroups.id, groupId), eq(messageGroups.userId, this.userId)));
  }

  async updateMetadata(
    groupId: string,
    metadata: Partial<CompressionGroupMetadata>,
  ): Promise<void> {
    const existing = await this.db
      .select({ metadata: messageGroups.metadata })
      .from(messageGroups)
      .where(and(eq(messageGroups.id, groupId), eq(messageGroups.userId, this.userId)));

    const existingData = (existing[0]?.metadata as Record<string, unknown>) || {};
    const newMetadata = { ...existingData, ...metadata };

    await this.db
      .update(messageGroups)
      .set({ metadata: newMetadata, updatedAt: new Date() })
      .where(and(eq(messageGroups.id, groupId), eq(messageGroups.userId, this.userId)));
  }

  async markMessagesAsCompressed(messageIds: string[], groupId: string): Promise<void> {
    if (messageIds.length === 0) return;

    await this.db
      .update(messages)
      .set({ messageGroupId: groupId })
      .where(and(eq(messages.userId, this.userId), inArray(messages.id, messageIds)));
  }

  async unmarkMessagesFromCompression(messageIds: string[]): Promise<void> {
    if (messageIds.length === 0) return;

    await this.db
      .update(messages)
      .set({ messageGroupId: null })
      .where(and(eq(messages.userId, this.userId), inArray(messages.id, messageIds)));
  }

  async toggleMessagePin(messageId: string, pinned: boolean): Promise<void> {
    const [message] = await this.db
      .select({ metadata: messages.metadata })
      .from(messages)
      .where(and(eq(messages.id, messageId), eq(messages.userId, this.userId)));

    if (!message) return;

    const currentMetadata = (message.metadata as Record<string, unknown>) || {};
    const newMetadata = { ...currentMetadata, pinned };

    await this.db
      .update(messages)
      .set({ metadata: newMetadata })
      .where(and(eq(messages.id, messageId), eq(messages.userId, this.userId)));
  }

  async getUncompressedMessages(topicId: string) {
    return this.db
      .select()
      .from(messages)
      .where(
        and(
          eq(messages.userId, this.userId),
          eq(messages.topicId, topicId),
          isNull(messages.messageGroupId),
        ),
      )
      .orderBy(messages.createdAt);
  }

  async getCompressedMessages(groupId: string) {
    return this.db
      .select()
      .from(messages)
      .where(and(eq(messages.userId, this.userId), eq(messages.messageGroupId, groupId)))
      .orderBy(messages.createdAt);
  }

  async deleteCompressionGroup(groupId: string): Promise<void> {
    await this.db
      .update(messages)
      .set({ messageGroupId: null })
      .where(and(eq(messages.userId, this.userId), eq(messages.messageGroupId, groupId)));

    await this.db
      .delete(messageGroups)
      .where(and(eq(messageGroups.id, groupId), eq(messageGroups.userId, this.userId)));
  }
}
