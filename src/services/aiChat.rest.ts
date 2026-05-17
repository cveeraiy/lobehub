/**
 * AI Chat service — REST API version.
 *
 * Drop-in replacement for `src/services/aiChat.ts` (TRPC version).
 * Calls the Python backend's `/api/ai-chat/*` REST endpoints directly.
 */
import { type SendMessageServerParams, type StructureOutputParams } from '@lobechat/types';
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

class AiChatService {
  sendMessageInServer = async (
    params: SendMessageServerParams,
    abortController: AbortController,
  ) => {
    return restClient.post('/ai-chat/send-message', {
      body: cleanObject(sendMessageBody(params)),
      signal: abortController?.signal,
    });
  };

  generateJSON = async (params: StructureOutputParams, abortController: AbortController) => {
    return restClient.post('/ai-chat/output-json', {
      body: params,
      signal: abortController?.signal,
    });
  };
}

export const aiChatService = new AiChatService();
