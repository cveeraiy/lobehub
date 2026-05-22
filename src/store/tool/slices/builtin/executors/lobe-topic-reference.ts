import { TopicReferenceExecutor } from '@lobechat/builtin-tool-topic-reference/executor';
import type { BuiltinToolResult } from '@lobechat/types';

import { topicService } from '@/services/topic';

interface GetTopicContextParams {
  topicId: string;
}

class TopicReferenceExecutionRuntime {
  getTopicContext = async (params: GetTopicContextParams): Promise<BuiltinToolResult> => {
    const { topicId } = params;

    if (!topicId) {
      return { content: 'topicId is required', success: false };
    }

    try {
      const result = await topicService.getTopicContext(topicId);
      return { content: result.content, success: result.success };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return { content: `Failed to fetch topic context: ${errorMessage}`, success: false };
    }
  };
}

const runtime = new TopicReferenceExecutionRuntime();

export const topicReferenceExecutor = new TopicReferenceExecutor(runtime);
