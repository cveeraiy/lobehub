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

interface RestMessage {
  agent_id?: string | null;
  content?: string | null;
  created_at?: string | null;
  error?: ChatMessageError | null;
  id: string;
  message_group_id?: string | null;
  metadata?: MessageMetadata | null;
  model?: string | null;
  parent_id?: string | null;
  provider?: string | null;
  role: UIChatMessage['role'];
  session_id?: string | null;
  thread_id?: string | null;
  tool_call_id?: string | null;
  tools?: UIChatMessage['tools'] | null;
  topic_id?: string | null;
  updated_at?: string | null;
}

const toTimestamp = (value?: string | null) => (value ? Date.parse(value) : Date.now());

const normalizeMessage = (message: RestMessage): UIChatMessage => ({
  agentId: message.agent_id ?? undefined,
  content: message.content ?? '',
  createdAt: toTimestamp(message.created_at),
  error: message.error ?? undefined,
  groupId: message.message_group_id ?? undefined,
  id: message.id,
  metadata: message.metadata ?? undefined,
  model: message.model ?? undefined,
  parentId: message.parent_id ?? undefined,
  provider: message.provider ?? undefined,
  role: message.role,
  sessionId: message.session_id ?? undefined,
  threadId: message.thread_id ?? undefined,
  tool_call_id: message.tool_call_id ?? undefined,
  tools: message.tools ?? undefined,
  topicId: message.topic_id ?? undefined,
  updatedAt: toTimestamp(message.updated_at ?? message.created_at),
});

const queryParams = (params?: MessageQueryContext) => ({
  agent_id: params?.agentId,
  group_id: params?.groupId,
  thread_id: params?.threadId ?? undefined,
  topic_id: params?.topicId ?? undefined,
  topic_share_id: params?.topicShareId,
});

const createBody = (params: CreateMessageParams) => ({
  agent_id: params.agentId,
  content: params.content,
  error: params.error ?? undefined,
  metadata: params.metadata,
  model: params.model,
  parent_id: params.parentId,
  provider: params.provider,
  role: params.role,
  session_id: params.sessionId,
  thread_id: params.threadId ?? undefined,
  tool_call_id: params.tool_call_id,
  tools: params.tools,
  topic_id: params.topicId,
});

const updateBody = (value: Partial<UpdateMessageParams>) => ({
  content: value.content,
  error: value.error ?? undefined,
  model: value.model,
  provider: value.provider,
  tools: value.tools,
});

const pluginBody = (value: Partial<Omit<MessagePluginItem, 'id'>>) => ({
  api_name: value.apiName,
  arguments: value.arguments,
  error: value.error,
  identifier: value.identifier,
  state: value.state,
  tool_call_id: value.toolCallId,
  type: value.type,
});

const compressionBody = (params: {
  agentId: string;
  groupId?: string | null;
  messageGroupId?: string;
  messageIds?: string[];
  threadId?: string | null;
  topicId: string;
}) => ({
  agent_id: params.agentId,
  group_id: params.groupId ?? undefined,
  message_group_id: params.messageGroupId,
  message_ids: params.messageIds,
  thread_id: params.threadId ?? undefined,
  topic_id: params.topicId,
});

export class MessageService {
  createMessage = async (params: CreateMessageParams): Promise<CreateMessageResult> => {
    return restClient.post<CreateMessageResult>('/messages', { body: createBody(params) });
  };

  getMessages = async (params: MessageQueryContext): Promise<UIChatMessage[]> => {
    const messages = await restClient.get<RestMessage[]>('/messages', {
      params: queryParams(params),
    });
    return messages.map(normalizeMessage);
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
    const res = await restClient.get<{ words: number }>('/messages/count-words', {
      params: params as any,
    });
    return res.words;
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

    return restClient.put<UpdateMessageResult>(`/messages/${id}`, {
      body: { error },
      params: queryParams(ctx),
    });
  };

  updateMessagePluginArguments = async (id: string, value: string | Record<string, any>) => {
    const args = typeof value === 'string' ? value : JSON.stringify(value);
    return restClient.put(`/messages/${id}/plugin`, { body: { arguments: args } });
  };

  updateToolArguments = async (
    toolCallId: string,
    value: string | Record<string, unknown>,
    ctx?: MessageQueryContext,
  ): Promise<{ messages?: UIChatMessage[]; success: boolean }> => {
    return restClient.put<{ messages?: UIChatMessage[]; success: boolean }>(
      '/messages/tool-arguments',
      {
        body: { tool_call_id: toolCallId, value },
        params: queryParams(ctx),
      },
    );
  };

  updateMessage = async (
    id: string,
    value: Partial<UpdateMessageParams>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}`, {
      body: updateBody(value),
      params: queryParams(ctx),
    });
  };

  updateMessageTranslate = async (id: string, translate: Partial<ChatTranslate> | false) => {
    return restClient.put(`/messages/${id}/translate`, {
      body:
        translate === false
          ? undefined
          : { content: translate.content, from_lang: translate.from, to: translate.to },
      params: { remove: translate === false ? true : undefined },
    });
  };

  updateMessageTTS = async (id: string, tts: Partial<ChatTTS> | false) => {
    return restClient.put(`/messages/${id}/tts`, {
      body:
        tts === false
          ? undefined
          : { content_md5: tts.contentMd5, file: tts.file, voice: tts.voice },
      params: { remove: tts === false ? true : undefined },
    });
  };

  updateMessageMetadata = async (
    id: string,
    value: Partial<MessageMetadata>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/metadata`, {
      body: value,
      params: queryParams(ctx),
    });
  };

  updateMessagePluginState = async (
    id: string,
    value: Record<string, any>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin-state`, {
      body: value,
      params: queryParams(ctx),
    });
  };

  updateMessagePluginError = async (
    id: string,
    error: ChatMessagePluginError | null,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin-error`, {
      body: error,
      params: queryParams(ctx),
    });
  };

  updateMessagePlugin = async (
    id: string,
    value: Partial<Omit<MessagePluginItem, 'id'>>,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/plugin`, {
      body: pluginBody(value),
      params: queryParams(ctx),
    });
  };

  updateMessageRAG = async (
    id: string,
    data: UpdateMessageRAGParams,
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.put<UpdateMessageResult>(`/messages/${id}/rag`, {
      body: {
        rag_query_id: data.ragQueryId,
      },
      params: queryParams(ctx),
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
    return restClient.put<UpdateMessageResult>(`/messages/${id}/tool-message`, {
      body: {
        content: value.content,
        metadata: value.metadata,
        plugin_error: value.pluginError,
        plugin_state: value.pluginState,
      },
      params: queryParams(ctx),
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
    return restClient.post<UpdateMessageResult>('/messages/remove-batch', {
      body: { ...ctx, ids },
    });
  };

  removeMessagesByAssistant = async (sessionId: string, topicId?: string) => {
    return restClient.post('/messages/remove-by-assistant', {
      params: { session_id: sessionId, topic_id: topicId },
    });
  };

  removeMessagesByGroup = async (groupId: string, topicId?: string) => {
    return restClient.post('/messages/remove-by-group', {
      params: { group_id: groupId, topic_id: topicId },
    });
  };

  removeAllMessages = async () => {
    return restClient.post('/messages/remove-all');
  };

  addFilesToMessage = async (
    id: string,
    fileIds: string[],
    ctx?: MessageQueryContext,
  ): Promise<UpdateMessageResult> => {
    return restClient.post<UpdateMessageResult>(`/messages/${id}/files`, {
      body: { file_ids: fileIds },
      params: queryParams(ctx),
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
    const result = await restClient.post<{ message_group_id: string }>(
      '/messages/compression-group',
      {
        body: compressionBody({ ...params, messageIds: params.messageIds }),
      },
    );

    return {
      messageGroupId: result.message_group_id,
      messages: [],
      messagesToSummarize: [],
    };
  };

  finalizeCompression = async (params: {
    agentId: string;
    content: string;
    groupId?: string | null;
    messageGroupId: string;
    threadId?: string | null;
    topicId: string;
  }): Promise<{ messages?: UIChatMessage[] }> => {
    await restClient.post('/messages/compression-group/finalize', {
      body: { ...compressionBody(params), content: params.content },
    });

    return { messages: [] };
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
    await restClient.put(`/messages/${params.messageGroupId}/group-metadata`, {
      body: { context: params.context, expanded: params.expanded },
    });

    return { messages: [] };
  };

  cancelCompression = async (params: {
    agentId: string;
    groupId?: string | null;
    messageGroupId: string;
    threadId?: string | null;
    topicId: string;
  }): Promise<{ messages: UIChatMessage[] }> => {
    await restClient.post('/messages/compression-group/cancel', { body: compressionBody(params) });

    return { messages: [] };
  };
}

export const messageService = new MessageService();
