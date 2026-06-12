import type {
  ChatTopic,
  ExecAgentAppContext,
  ExecAgentResult,
  ExecSubAgentTaskResult,
  TaskStatusResult,
  UIChatMessage,
} from '@lobechat/types';

import { restClient } from '@/libs/rest';

export type { ExecAgentResult };

export interface ResumeApprovalParam {
  decision: 'approved' | 'rejected' | 'rejected_continue';
  parentMessageId: string;
  rejectionReason?: string;
  toolCallId: string;
}

export interface ExecAgentTaskParams {
  agentId?: string;
  appContext?: ExecAgentAppContext;
  autoStart?: boolean;
  clientRuntime?: 'desktop' | 'web';
  deviceId?: string;
  existingMessageIds?: string[];
  fileIds?: string[];
  parentMessageId?: string;
  prompt: string;
  resumeApproval?: ResumeApprovalParam;
  slug?: string;
}

export interface ExecGroupAgentParams {
  agentId: string;
  files?: string[];
  groupId: string;
  message: string;
  newTopic?: {
    title?: string;
    topicMessageIds?: string[];
  };
  topicId?: string | null;
}

export interface ExecGroupAgentResult {
  assistantMessageId: string;
  error?: string | null;
  isCreateNewTopic?: boolean;
  messages?: UIChatMessage[];
  operationId: string;
  success: boolean;
  topicId?: string | null;
  topics?: {
    items: ChatTopic[];
    total: number;
  };
  userMessageId: string;
}

export interface ExecSubAgentTaskParams {
  agentId: string;
  groupId?: string;
  instruction: string;
  parentMessageId: string;
  parentOperationId?: string;
  timeout?: number;
  title?: string;
  topicId: string;
}

export interface GetSubAgentTaskStatusParams {
  threadId: string;
}

export interface InterruptTaskParams {
  operationId?: string;
  threadId?: string;
}

export interface CreateClientTaskThreadParams {
  agentId: string;
  groupId?: string;
  instruction: string;
  parentMessageId: string;
  title?: string;
  topicId: string;
}

export interface CreateClientGroupAgentTaskThreadParams {
  groupId: string;
  instruction: string;
  parentMessageId: string;
  subAgentId: string;
  title?: string;
  topicId: string;
}

export interface UpdateClientTaskThreadStatusParams {
  completionReason: 'done' | 'error' | 'interrupted';
  error?: string;
  metadata?: {
    totalCost?: number;
    totalMessages?: number;
    totalSteps?: number;
    totalTokens?: number;
    totalToolCalls?: number;
  };
  resultContent?: string;
  threadId: string;
}

export interface CreateClientTaskThreadResult {
  messages: UIChatMessage[];
  startedAt: string;
  success: boolean;
  threadId: string;
  threadMessages: UIChatMessage[];
  userMessageId: string;
}

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
  }) as unknown as ExecAgentResult;

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

  async execSubAgentTask(params: ExecSubAgentTaskParams): Promise<ExecSubAgentTaskResult> {
    return restClient.post<ExecSubAgentTaskResult>('/ai-agent/exec-sub-agent', {
      body: subAgentBody(params),
    });
  }

  async getSubAgentTaskStatus(params: GetSubAgentTaskStatusParams): Promise<TaskStatusResult> {
    return restClient.get<TaskStatusResult>('/ai-agent/sub-agent-task-status', {
      params: { threadId: params.threadId },
    });
  }

  async interruptTask(
    params: InterruptTaskParams,
  ): Promise<{ operationId?: string; success: boolean }> {
    return restClient.post<{ operationId?: string; success: boolean }>('/ai-agent/interrupt', {
      body: { operation_id: params.operationId, thread_id: params.threadId },
    });
  }

  async createClientTaskThread(
    params: CreateClientTaskThreadParams,
  ): Promise<CreateClientTaskThreadResult> {
    return restClient.post<CreateClientTaskThreadResult>('/ai-agent/create-client-task-thread', {
      body: clientTaskBody(params),
    });
  }

  async createClientGroupAgentTaskThread(
    params: CreateClientGroupAgentTaskThreadParams,
  ): Promise<CreateClientTaskThreadResult> {
    return restClient.post<CreateClientTaskThreadResult>(
      '/ai-agent/create-client-group-agent-task-thread',
      {
        body: clientGroupTaskBody(params),
      },
    );
  }

  async updateClientTaskThreadStatus(
    params: UpdateClientTaskThreadStatusParams,
  ): Promise<{ success: boolean }> {
    return restClient.post<{ success: boolean }>('/ai-agent/update-client-task-thread-status', {
      body: updateThreadStatusBody(params),
    });
  }
}

export const aiAgentService = new AiAgentService();
