import {
  type ChatMessageError,
  type ChatMessagePluginError,
  type ChatTranslate,
  type ChatTTS,
  type CreateMessageParams,
  type CreateMessageResult,
  type MessageMetadata,
  type MessagePluginItem,
  type ModelRankItem,
  type UIChatMessage,
  type UpdateMessageParams,
  type UpdateMessageRAGParams,
  type UpdateMessageResult,
} from '@lobechat/types';
import { type HeatmapsProps } from '@lobehub/charts';

import { restClient } from '@/libs/rest';

/**
 * Query context for message operations
 */
export interface MessageQueryContext {
  agentId?: string;
  groupId?: string;
  threadId?: string | null;
  topicId?: string | null;
  topicShareId?: string;
}

export class MessageService {
  createMessage = async (params: CreateMessageParams): Promise<CreateMessageResult> => {
    return restClient.post<CreateMessageResult>('/messages', { body: params });
  };

  getMessages = async (params: MessageQueryContext): Promise<UIChatMessage[]> => {
    return restClient.get<UIChatMessage[]>('/messages', {
      params: {
        agent_id: params.agentId,
        group_id: params.groupId,
        thread_id: params.threadId ?? undefined,
        topic_id: params.topicId ?? undefined,
        topic_share_id: params.topicShareId,
      } as any,
    });
  };

  countMessages = async (params?: {
    endDate?: string;
    range?: [string, string];
    startDate?: string;
  }): Promise<number> => {
    const res = await restClient.get<{ count: number }>('/messages/count', {
      params: params as any,
    });
    return res.count;
  };

  countWords = async (params?: {
    endDate?: string;
    range?: [string, string];
    startDate?: string;
  }): Promise<number> => {
    const res = await restClient.get<{ count: number }>('/messages/count-words', {
      params: params as any,
    });
    return res.count;
  };

  rankModels = async (): Promise<ModelRankItem[]> => {
    return restClient.get<ModelRankItem[]>('/messages/rank-models');
  };

  getHeatmaps = async (): Promise<HeatmapsProps['data']> => {
    return restClient.get('/messages/heatmaps');
  };

  updateMessageError = async (id: string, value: ChatMessageError, ctx?: MessageQueryContext) => {
    const error = value.type
      ? value
      : { body: value, message: value.message, type: 'ApplicationRuntimeError' };

    return restClient.put(`/messages/${id}`, {
      body: { ...ctx, value: { error } },
    });
  };

  updateMessagePluginArguments = async (id: string, value: string | Record<string, any>) => {
    const args = typeof value === 'string' ? value : JSON.stringify(value);
    return restClient.put(`/messages/${id}/plugin`, { body: { value: { arguments: args } } });
  };

  updateToolArguments = async (
    toolCallId: string,
    value: string | Record<string, unknown>,
    ctx?: MessageQueryContext,
  ) => {
    return restClient.put('/messages/tool-arguments', {
      body: { ...ctx, toolCallId, value },
    });
  };

  updateMessage = async (
    id: string,
    value: Partial<UpdateMessageParams>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}`, {
      body: { ...ctx, value },
    });
  };

  updateMessageTranslate = async (id: string, translate: Partial<ChatTranslate> | false) => {
    return restClient.put(`/messages/${id}/translate`, { body: { value: translate } });
  };

  updateMessageTTS = async (id: string, tts: Partial<ChatTTS> | false) => {
    return restClient.put(`/messages/${id}/tts`, { body: { value: tts } });
  };

  updateMessageMetadata = async (
    id: string,
    value: Partial<MessageMetadata>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/metadata`, {
      body: { ...ctx, value },
    });
  };

  updateMessagePluginState = async (
    id: string,
    value: Record<string, any>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin-state`, {
      body: { ...ctx, value },
    });
  };

  updateMessagePluginError = async (
    id: string,
    error: ChatMessagePluginError | null,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin-error`, {
      body: { ...ctx, value: error },
    });
  };

  updateMessagePlugin = async (
    id: string,
    value: Partial<Omit<MessagePluginItem, 'id'>>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin`, {
      body: { ...ctx, value },
    });
  };

  updateMessageRAG = async (
    id: string,
    data: UpdateMessageRAGParams,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/rag`, {
      body: { ...ctx, value: data },
    });
  };

  updateToolMessage = async (
    id: string,
    value: {
      content?: string;
      metadata?: Record<string, any>;
      pluginError?: any;
      pluginState?: Record<string, any>;
    },
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/tool`, {
      body: { ...ctx, value },
    });
  };

  removeMessage = async (id: string, ctx?: MessageQueryContext): Promise<UpdateMessageResult> => {
    return restClient.delete<UpdateMessageResult>(`/messages/${id}`, {
      body: ctx,
    });
  };

  removeMessages = async (
    ids: string[],
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.post<UpdateMessageResult>('/messages/batch-delete', {
      body: { ...ctx, ids },
    });
  };

  removeMessagesByAssistant = async (sessionId: string, topicId?: string) => {
    return restClient.delete('/messages', {
      params: { session_id: sessionId, topic_id: topicId } as any,
    });
  };

  removeMessagesByGroup = async (groupId: string, topicId?: string) => {
    return restClient.delete('/messages', {
      params: { group_id: groupId, topic_id: topicId } as any,
    });
  };

  removeAllMessages = async () => {
    return restClient.delete('/messages');
  };

  addFilesToMessage = async (
    id: string,
    fileIds: string[],
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.post<UpdateMessageResult>(`/messages/${id}/files`, {
      body: { ...ctx, fileIds },
    });
  };

  // =============== Compression ===============

  createCompressionGroup = async (params: {
    agentId: string;
    groupId?: string | null;
    messageIds: string[];
    threadId?: string | null;
    topicId: string;
  }): Promise<{
    messageGroupId: string;
    messages: UIChatMessage[];
    messagesToSummarize: UIChatMessage[];
  }> => {
    return restClient.post('/messages/compression-group', { body: params });
  };

  finalizeCompression = async (params: {
    agentId: string;
    content: string;
    groupId?: string | null;
    messageGroupId: string;
    threadId?: string | null;
    topicId: string;
  }): Promise<{ messages?: UIChatMessage[] }> => {
    return restClient.post('/messages/compression-group/finalize', { body: params });
  };

  updateMessageGroupMetadata = async (params: {
    context: {
      agentId: string;
      groupId?: string | null;
      threadId?: string | null;
      topicId: string;
    };
    expanded?: boolean;
    messageGroupId: string;
  }): Promise<{ messages: UIChatMessage[] }> => {
    return restClient.put('/messages/group-metadata', { body: params });
  };

  cancelCompression = async (params: {
    agentId: string;
    groupId?: string | null;
    messageGroupId: string;
    threadId?: string | null;
    topicId: string;
  }): Promise<{ messages: UIChatMessage[] }> => {
    return restClient.post('/messages/compression-group/cancel', { body: params });
  };
}

export const messageService = new MessageService();
