import type { BuiltinToolContext, BuiltinToolManifest, BuiltinToolResult } from '@lobechat/types';
import { BaseExecutor } from '@lobechat/types';

export const TopicReferenceIdentifier = 'lobe-topic-reference';

export const TopicReferenceApiName = {
  getTopicContext: 'getTopicContext',
} as const;

export type TopicReferenceApiNameType =
  (typeof TopicReferenceApiName)[keyof typeof TopicReferenceApiName];

export const TopicReferenceManifest: BuiltinToolManifest = {
  api: [
    {
      description:
        'Retrieve context from a referenced topic conversation. Returns the topic summary if available, otherwise returns the most recent messages. Use this when you see a topic reference tag in the user message and need to understand what was discussed in that topic.',
      name: TopicReferenceApiName.getTopicContext,
      parameters: {
        additionalProperties: false,
        properties: {
          topicId: {
            description: 'The ID of the topic to retrieve context from',
            type: 'string',
          },
        },
        required: ['topicId'],
        type: 'object',
      },
    },
  ],
  identifier: TopicReferenceIdentifier,
  meta: {
    avatar: '📋',
    description: 'Retrieve context from referenced topic conversations',
    title: 'Topic Reference',
  },
  systemRole: '',
  type: 'builtin',
};

interface GetTopicContextParams {
  topicId: string;
}

interface TopicReferenceExecutionRuntime {
  getTopicContext: (params: GetTopicContextParams) => Promise<BuiltinToolResult>;
}

export class TopicReferenceExecutor extends BaseExecutor<typeof TopicReferenceApiName> {
  readonly identifier = TopicReferenceIdentifier;
  protected readonly apiEnum = TopicReferenceApiName;
  private runtime: TopicReferenceExecutionRuntime;

  constructor(runtime: TopicReferenceExecutionRuntime) {
    super();
    this.runtime = runtime;
  }

  getTopicContext = async (
    params: GetTopicContextParams,
    _ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    return this.runtime.getTopicContext(params);
  };
}
