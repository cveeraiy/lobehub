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
  ExecSubAgentTaskParams,
  GetSubAgentTaskStatusParams,
  InterruptTaskParams,
  ResumeApprovalParam,
  UpdateClientTaskThreadStatusParams,
} from './aiAgent';

export type { ExecAgentResult, ResumeApprovalParam };

class AiAgentService {
  async execAgentTask(params: ExecAgentTaskParams): Promise<ExecAgentResult> {
    return restClient.post<ExecAgentResult>('/ai-agent/exec', { body: params });
  }

  async refreshGatewayToken(topicId: string): Promise<{ token: string }> {
    return restClient.get<{ token: string }>('/ai-agent/refresh-gateway-token', {
      params: { topicId },
    });
  }

  async execSubAgentTask(params: ExecSubAgentTaskParams) {
    return restClient.post('/ai-agent/exec-sub-agent', { body: params });
  }

  async getSubAgentTaskStatus(params: GetSubAgentTaskStatusParams) {
    return restClient.get('/ai-agent/sub-agent-task-status', {
      params: { threadId: params.threadId },
    });
  }

  async interruptTask(params: InterruptTaskParams) {
    return restClient.post('/ai-agent/interrupt', { body: params });
  }

  async createClientTaskThread(params: CreateClientTaskThreadParams) {
    return restClient.post('/ai-agent/create-client-task-thread', { body: params });
  }

  async createClientGroupAgentTaskThread(params: CreateClientGroupAgentTaskThreadParams) {
    return restClient.post('/ai-agent/create-client-group-agent-task-thread', { body: params });
  }

  async updateClientTaskThreadStatus(params: UpdateClientTaskThreadStatusParams) {
    return restClient.post('/ai-agent/update-client-task-thread-status', { body: params });
  }
}

export const aiAgentService = new AiAgentService();
