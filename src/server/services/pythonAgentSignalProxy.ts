import { callPythonBackend } from '@/server/utils/pythonBackend';

export interface PythonAgentSignalSourceEvent {
  agentId?: string;
  dedupKey?: string;
  payload?: Record<string, unknown>;
  scope?: string;
  scopeKey?: string;
  source?: string;
  sourceId?: string;
  sourceType?: string;
  timestamp?: number;
  type?: string;
}

export async function emitPythonAgentSignalSourceEvent(
  input: PythonAgentSignalSourceEvent,
  context: { agentId?: string; userId: string },
): Promise<unknown> {
  return callPythonBackend('/api/agent-signal/emit', context.userId, { body: input });
}
