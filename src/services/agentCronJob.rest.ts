import {
  type AgentCronJob,
  type CreateAgentCronJobData,
  type UpdateAgentCronJobData,
} from '@/database/schemas/agentCronJob';
import { restClient } from '@/libs/rest';

interface ServiceResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

class AgentCronJobService {
  async create(
    data: Omit<CreateAgentCronJobData, 'userId'> & { templateId?: string },
  ): Promise<ServiceResponse<AgentCronJob>> {
    return restClient.post('/agent-cron-jobs', { body: data });
  }

  async getByAgentId(agentId: string): Promise<ServiceResponse<AgentCronJob[]>> {
    return restClient.get(`/agent-cron-jobs/agent/${agentId}`);
  }

  async getById(id: string): Promise<ServiceResponse<AgentCronJob>> {
    return restClient.get(`/agent-cron-jobs/${id}`);
  }

  async list(
    options: {
      agentId?: string;
      enabled?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ) {
    return restClient.get('/agent-cron-jobs', {
      params: {
        agent_id: options.agentId,
        enabled: options.enabled,
        limit: options.limit,
        offset: options.offset,
      },
    });
  }

  async update(id: string, data: UpdateAgentCronJobData): Promise<ServiceResponse<AgentCronJob>> {
    return restClient.put(`/agent-cron-jobs/${id}`, { body: data });
  }

  async delete(id: string): Promise<{ message?: string; success: boolean }> {
    return restClient.delete(`/agent-cron-jobs/${id}`);
  }

  async resetExecutions(
    id: string,
    newMaxExecutions?: number,
  ): Promise<ServiceResponse<AgentCronJob>> {
    return restClient.post('/agent-cron-jobs/reset-executions', {
      body: { id, newMaxExecutions },
    });
  }

  async getStats() {
    return restClient.get('/agent-cron-jobs/stats');
  }

  async getNearDepletion(threshold: number = 5) {
    return restClient.get('/agent-cron-jobs/near-depletion', {
      params: { threshold } as any,
    });
  }

  async batchUpdateStatus(ids: string[], enabled: boolean) {
    return restClient.post('/agent-cron-jobs/batch-update-status', {
      body: { enabled, ids },
    });
  }
}

export const agentCronJobService = new AgentCronJobService();
