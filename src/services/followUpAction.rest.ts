import type { FollowUpExtractInput, FollowUpExtractResult } from '@lobechat/types';

import { restClient } from '@/libs/rest';

class FollowUpActionService {
  async extract(
    input: FollowUpExtractInput,
    signal?: AbortSignal,
  ): Promise<FollowUpExtractResult | null> {
    try {
      const result = await restClient.post<FollowUpExtractResult>('/follow-up/extract', {
        body: input,
        signal,
      });
      return result;
    } catch (err) {
      if (signal?.aborted) return null;
      if (err instanceof DOMException && err.name === 'AbortError') return null;
      console.warn('[FollowUpAction] extract failed', err);
      return null;
    }
  }
}

export const followUpActionService = new FollowUpActionService();
