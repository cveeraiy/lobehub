/**
 * AI Chat service — REST API version.
 *
 * Drop-in replacement for `src/services/aiChat.ts` (TRPC version).
 * Calls the Python backend's `/api/ai-chat/*` REST endpoints directly.
 */
import { type SendMessageServerParams, type StructureOutputParams } from '@lobechat/types';
import { cleanObject } from '@lobechat/utils';

import { restClient } from '@/libs/rest';

class AiChatService {
  sendMessageInServer = async (
    params: SendMessageServerParams,
    abortController: AbortController,
  ) => {
    return restClient.post('/ai-chat/send-message', {
      body: cleanObject(params),
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
