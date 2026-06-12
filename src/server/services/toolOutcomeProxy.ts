import { emitPythonAgentSignalSourceEvent } from '@/server/services/pythonAgentSignalProxy';

export const redisPolicyStateStore = {};

export const resolveToolOutcomeScope = (input: {
  agentId?: string;
  taskId?: string;
  topicId?: string;
  userId: string;
}) => {
  if (input.taskId) return { scope: 'task', scopeKey: input.taskId };
  if (input.topicId) return { scope: 'topic', scopeKey: input.topicId };
  if (input.agentId) return { scope: 'agent', scopeKey: input.agentId };

  return { scope: 'user', scopeKey: input.userId };
};

export const emitToolOutcomeSafely = async (input: Record<string, any>) => {
  const context = input.context as { agentId?: string; userId?: string } | undefined;
  if (!context?.userId) return;

  await emitPythonAgentSignalSourceEvent(
    {
      agentId: context.agentId,
      dedupKey: [
        input.identifier,
        input.toolAction,
        input.toolCallId,
        input.operationId,
        input.status,
      ]
        .filter(Boolean)
        .join(':'),
      payload: input,
      scope: input.scope,
      scopeKey: input.scopeKey,
      source: 'tool-outcome',
      sourceId: input.toolCallId ?? input.operationId,
      sourceType: 'tool_outcome',
      timestamp: Date.now(),
      type: 'tool_outcome',
    },
    { agentId: context.agentId, userId: context.userId },
  ).catch((error) => {
    console.error('[AgentSignal] Failed to emit tool outcome:', error);
  });
};
