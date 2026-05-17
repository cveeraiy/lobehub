import {
  type CreateAgentCronJobData,
  type UpdateAgentCronJobData,
} from '@/database/schemas/agentCronJob';
import { restClient } from '@/libs/rest';

class AgentCronJobService {
  async create(data: Omit<CreateAgentCronJobData, 'userId'> & { templateId?: string }) {
    return restClient.post('/agent-cron-jobs', { body: data });
  }

  async getByAgentId(agentId: string) {
    return restClient.get(`/agent-cron-jobs/agent/${agentId}`);
  }

  async getById(id: string) {
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

  async update(id: string, data: UpdateAgentCronJobData) {
    return restClient.put(`/agent-cron-jobs/${id}`, { body: data });
  }

  async delete(id: string) {
    return restClient.delete(`/agent-cron-jobs/${id}`);
  }

  async resetExecutions(id: string, newMaxExecutions?: number) {
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
