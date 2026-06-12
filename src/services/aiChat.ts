import type {
  MessageMetadata,
  SendMessageServerParams,
  SendMessageServerResponse,
  StructureOutputParams,
  UIChatMessage,
} from '@lobechat/types';
import { cleanObject } from '@lobechat/utils';

import { restClient } from '@/libs/rest';

const sendMessageBody = (params: SendMessageServerParams) => ({
  agent_id: params.agentId,
  group_id: params.groupId,
  new_assistant_message: {
    metadata: params.newAssistantMessage.metadata,
    model: params.newAssistantMessage.model,
    provider: params.newAssistantMessage.provider,
  },
  new_thread: params.newThread && {
    parent_thread_id: params.newThread.parentThreadId,
    source_message_id: params.newThread.sourceMessageId,
    title: params.newThread.title,
    type: params.newThread.type,
  },
  new_topic: params.newTopic && {
    metadata: params.newTopic.metadata,
    title: params.newTopic.title,
    topic_message_ids: params.newTopic.topicMessageIds,
    trigger: params.newTopic.trigger,
  },
  new_user_message: {
    content: params.newUserMessage.content,
    editor_data: params.newUserMessage.editorData,
    files: params.newUserMessage.files?.map((id) => ({ id })),
    metadata: params.newUserMessage.metadata,
    page_selections: params.newUserMessage.pageSelections,
    parent_id: params.newUserMessage.parentId,
  },
  preload_messages: params.preloadMessages?.map((message) => ({
    content: message.content,
    metadata: message.metadata,
    plugin: message.plugin,
    role: message.role,
    tool_call_id: message.tool_call_id,
    tools: message.tools,
  })),
  session_id: params.sessionId,
  thread_id: params.threadId,
  topic_filter: params.topicFilter,
  topic_id: params.topicId,
});

interface RestMessage {
  agent_id?: string | null;
  content?: string | null;
  created_at?: string | null;
  error?: UIChatMessage['error'] | null;
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

interface SendMessageRestResponse {
  assistantMessageId?: string;
  createdThreadId?: string | null;
  isCreateNewTopic?: boolean;
  messages?: RestMessage[];
  topicId?: string | null;
  topics?: SendMessageServerResponse['topics'];
  userMessageId?: string;
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

const normalizeSendMessageResponse = (
  response: SendMessageRestResponse,
): SendMessageServerResponse => ({
  ...response,
  assistantMessageId: response.assistantMessageId ?? '',
  createdThreadId: response.createdThreadId ?? undefined,
  isCreateNewTopic: response.isCreateNewTopic ?? false,
  messages: Array.isArray(response.messages) ? response.messages.map(normalizeMessage) : [],
  topicId: response.topicId ?? '',
  userMessageId: response.userMessageId ?? '',
});

class AiChatService {
  sendMessageInServer = async (
    params: SendMessageServerParams,
    abortController: AbortController,
  ) => {
    const response = await restClient.post<SendMessageRestResponse>('/ai-chat/send-message', {
      body: cleanObject(sendMessageBody(params)),
      signal: abortController?.signal,
    });

    return normalizeSendMessageResponse(response);
  };

  generateJSON = async (params: StructureOutputParams, abortController: AbortController) => {
    return restClient.post('/ai-chat/output-json', {
      body: params,
      signal: abortController?.signal,
    });
  };
}

export const aiChatService = new AiChatService();
