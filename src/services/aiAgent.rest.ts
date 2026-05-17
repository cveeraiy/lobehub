/**
 * AI Agent service — REST API version.
 *
 * Drop-in replacement for `src/services/aiAgent.ts` (TRPC version).
 * Calls the Python backend's `/api/ai-agent/*` REST endpoints directly.
 */
import type { ExecAgentResult } from '@lobechat/types';

import { restClient } from '@/libs/rest';

import type {
  CreateClientGroupAgentTaskThreadParams,
  CreateClientTaskThreadParams,
  ExecAgentTaskParams,
  ExecGroupAgentParams,
  ExecGroupAgentResult,
  ExecSubAgentTaskParams,
  GetSubAgentTaskStatusParams,
  InterruptTaskParams,
  ResumeApprovalParam,
  UpdateClientTaskThreadStatusParams,
} from './aiAgent';

export type { ExecAgentResult, ResumeApprovalParam };

const appContextBody = (appContext: ExecAgentTaskParams['appContext']) =>
  appContext && {
    default_task_assignee_agent_id: appContext.defaultTaskAssigneeAgentId,
    document_id: appContext.documentId,
    group_id: appContext.groupId,
    scope: appContext.scope,
    session_id: appContext.sessionId,
    task_id: appContext.taskId,
    thread_id: appContext.threadId,
    topic_id: appContext.topicId,
  };

const resumeApprovalBody = (resumeApproval: ExecAgentTaskParams['resumeApproval']) =>
  resumeApproval && {
    decision: resumeApproval.decision,
    parent_message_id: resumeApproval.parentMessageId,
    rejection_reason: resumeApproval.rejectionReason,
    tool_call_id: resumeApproval.toolCallId,
  };

const execAgentBody = (params: ExecAgentTaskParams) => ({
  agent_id: params.agentId,
  app_context: appContextBody(params.appContext),
  auto_start: params.autoStart,
  client_runtime: params.clientRuntime,
  device_id: params.deviceId,
  existing_message_ids: params.existingMessageIds,
  file_ids: params.fileIds,
  parent_message_id: params.parentMessageId,
  prompt: params.prompt,
  resume_approval: resumeApprovalBody(params.resumeApproval),
  slug: params.slug,
});

const normalizeExecAgentResult = (result: Record<string, any>): ExecAgentResult =>
  ({
    assistantMessageId: result.assistantMessageId ?? result.assistant_message_id,
    autoStarted: result.autoStarted ?? result.auto_started,
    error: result.error,
    isCreateNewTopic: result.isCreateNewTopic ?? result.is_create_new_topic,
    message: result.message,
    operationId: result.operationId ?? result.operation_id,
    status: result.status,
    success: result.success,
    timestamp: result.timestamp,
    topicId: result.topicId ?? result.topic_id,
    userMessageId: result.userMessageId ?? result.user_message_id,
  }) as ExecAgentResult;

const execGroupBody = (params: ExecGroupAgentParams) => ({
  agent_id: params.agentId,
  file_ids: params.files,
  group_id: params.groupId,
  message: params.message,
  new_topic: params.newTopic && {
    title: params.newTopic.title,
    topic_message_ids: params.newTopic.topicMessageIds,
  },
  topic_id: params.topicId ?? undefined,
});

const normalizeExecGroupResult = (result: Record<string, any>): ExecGroupAgentResult => ({
  assistantMessageId: result.assistantMessageId ?? result.assistant_message_id,
  error: result.error,
  isCreateNewTopic: result.isCreateNewTopic ?? result.is_create_new_topic,
  messages: result.messages,
  operationId: result.operationId ?? result.operation_id,
  success: result.success,
  topicId: result.topicId ?? result.topic_id,
  topics: result.topics,
  userMessageId: result.userMessageId ?? result.user_message_id,
});

const subAgentBody = (params: ExecSubAgentTaskParams) => ({
  agent_id: params.agentId,
  group_id: params.groupId,
  instruction: params.instruction,
  parent_message_id: params.parentMessageId,
  parent_operation_id: params.parentOperationId,
  title: params.title,
  topic_id: params.topicId,
});

const clientTaskBody = (params: CreateClientTaskThreadParams) => ({
  agent_id: params.agentId,
  group_id: params.groupId,
  instruction: params.instruction,
  parent_message_id: params.parentMessageId,
  title: params.title,
  topic_id: params.topicId,
});

const clientGroupTaskBody = (params: CreateClientGroupAgentTaskThreadParams) => ({
  group_id: params.groupId,
  instruction: params.instruction,
  parent_message_id: params.parentMessageId,
  sub_agent_id: params.subAgentId,
  title: params.title,
  topic_id: params.topicId,
});

const updateThreadStatusBody = (params: UpdateClientTaskThreadStatusParams) => ({
  completion_reason: params.completionReason,
  error: params.error,
  metadata: params.metadata,
  result_content: params.resultContent,
  thread_id: params.threadId,
});

class AiAgentService {
  async execAgentTask(params: ExecAgentTaskParams): Promise<ExecAgentResult> {
    const result = await restClient.post<Record<string, any>>('/ai-agent/exec', {
      body: execAgentBody(params),
    });
    return normalizeExecAgentResult(result);
  }

  async execGroupAgent(
    params: ExecGroupAgentParams,
    signal?: AbortSignal,
  ): Promise<ExecGroupAgentResult> {
    const result = await restClient.post<Record<string, any>>('/ai-agent/exec-group', {
      body: execGroupBody(params),
      signal,
    });
    return normalizeExecGroupResult(result);
  }

  async refreshGatewayToken(topicId: string): Promise<{ token: string }> {
    return restClient.get<{ token: string }>('/ai-agent/refresh-gateway-token', {
      params: { topicId },
    });
  }

  async execSubAgentTask(params: ExecSubAgentTaskParams) {
    return restClient.post('/ai-agent/exec-sub-agent', { body: subAgentBody(params) });
  }

  async getSubAgentTaskStatus(params: GetSubAgentTaskStatusParams) {
    return restClient.get('/ai-agent/sub-agent-task-status', {
      params: { threadId: params.threadId },
    });
  }

  async interruptTask(params: InterruptTaskParams) {
    return restClient.post('/ai-agent/interrupt', {
      body: { operation_id: params.operationId, thread_id: params.threadId },
    });
  }

  async createClientTaskThread(params: CreateClientTaskThreadParams) {
    return restClient.post('/ai-agent/create-client-task-thread', { body: clientTaskBody(params) });
  }

  async createClientGroupAgentTaskThread(params: CreateClientGroupAgentTaskThreadParams) {
    return restClient.post('/ai-agent/create-client-group-agent-task-thread', {
      body: clientGroupTaskBody(params),
    });
  }

  async updateClientTaskThreadStatus(params: UpdateClientTaskThreadStatusParams) {
    return restClient.post('/ai-agent/update-client-task-thread-status', {
      body: updateThreadStatusBody(params),
    });
  }
}

export const aiAgentService = new AiAgentService();
