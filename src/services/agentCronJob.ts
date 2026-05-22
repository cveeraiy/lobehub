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

interface RestAgentCronJob {
  agent_id?: string;
  condition?: Record<string, any> | null;
  config?: Record<string, any> | null;
  created_at?: string | null;
  description?: string | null;
  enabled?: boolean | null;
  id: string;
  last_run_at?: string | null;
  name?: string | null;
  next_run_at?: string | null;
  schedule?: string | null;
  timezone?: string | null;
  total_failures?: number | null;
  total_runs?: number | null;
  updated_at?: string | null;
  user_id?: string;
}

interface RestServiceResponse<T> {
  data: T;
  message?: string;
  pagination?: {
    hasMore?: boolean;
    limit?: number;
    offset?: number;
    total?: number;
  };
  success: boolean;
}

interface CronJobStats {
  activeJobs: number;
  completedExecutions: number;
  pendingExecutions: number;
  totalJobs: number;
}

interface RestCronJobStats {
  enabledCount?: number;
  totalFailures?: number;
  totalJobs?: number;
  totalRuns?: number;
}

const toDate = (value: string | null | undefined): Date | null => (value ? new Date(value) : null);

const toCronJob = (job: RestAgentCronJob): AgentCronJob =>
  ({
    agentId: job.agent_id,
    content: (job.config?.content as string | undefined) ?? '',
    createdAt: toDate(job.created_at) ?? new Date(),
    cronPattern: job.schedule ?? '',
    description: job.description ?? null,
    editData: job.config?.editData ?? null,
    enabled: job.enabled ?? true,
    executionConditions: job.condition ?? null,
    groupId: (job.config?.groupId as string | undefined) ?? null,
    id: job.id,
    lastExecutedAt: toDate(job.last_run_at),
    maxExecutions: (job.config?.maxExecutions as number | undefined) ?? null,
    name: job.name ?? null,
    remainingExecutions: (job.config?.remainingExecutions as number | undefined) ?? null,
    timezone: job.timezone ?? 'UTC',
    totalExecutions: job.total_runs ?? 0,
    updatedAt: toDate(job.updated_at) ?? new Date(),
    userId: job.user_id,
  }) as AgentCronJob;

const toCronJobResponse = (
  response: RestServiceResponse<RestAgentCronJob>,
): ServiceResponse<AgentCronJob> => ({
  ...response,
  data: toCronJob(response.data),
});

const toCronJobListResponse = (
  response: RestServiceResponse<RestAgentCronJob[]>,
): RestServiceResponse<AgentCronJob[]> => ({
  ...response,
  data: response.data.map(toCronJob),
});

const compact = <T extends Record<string, any>>(value: T): Partial<T> =>
  Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined)) as Partial<T>;

const toRestBody = (
  data: Partial<CreateAgentCronJobData & UpdateAgentCronJobData> & { templateId?: string },
) => {
  const config = compact({
    content: data.content,
    editData: data.editData,
    groupId: data.groupId,
    maxExecutions: data.maxExecutions,
    remainingExecutions: data.remainingExecutions,
  });

  return compact({
    agent_id: data.agentId,
    condition: data.executionConditions,
    config: Object.keys(config).length > 0 ? config : undefined,
    description: data.description,
    enabled: data.enabled,
    name: data.name,
    schedule: data.cronPattern,
    template_id: data.templateId,
    timezone: data.timezone,
  });
};

class AgentCronJobService {
  async create(
    data: Omit<CreateAgentCronJobData, 'userId'> & { templateId?: string },
  ): Promise<ServiceResponse<AgentCronJob>> {
    const response = await restClient.post<RestServiceResponse<RestAgentCronJob>>(
      '/agent-cron-jobs',
      { body: toRestBody(data) },
    );
    return toCronJobResponse(response);
  }

  async getByAgentId(agentId: string): Promise<ServiceResponse<AgentCronJob[]>> {
    const response = await restClient.get<RestServiceResponse<RestAgentCronJob[]>>(
      `/agent-cron-jobs/agent/${agentId}`,
    );
    return toCronJobListResponse(response);
  }

  async getById(id: string): Promise<ServiceResponse<AgentCronJob>> {
    const response = await restClient.get<RestServiceResponse<RestAgentCronJob>>(
      `/agent-cron-jobs/${id}`,
    );
    return toCronJobResponse(response);
  }

  async list(
    options: {
      agentId?: string;
      enabled?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<RestServiceResponse<AgentCronJob[]>> {
    const response = await restClient.get<RestServiceResponse<RestAgentCronJob[]>>(
      '/agent-cron-jobs',
      {
        params: {
          agent_id: options.agentId,
          enabled: options.enabled,
          limit: options.limit,
          offset: options.offset,
        },
      },
    );
    return toCronJobListResponse(response);
  }

  async update(id: string, data: UpdateAgentCronJobData): Promise<ServiceResponse<AgentCronJob>> {
    const response = await restClient.put<RestServiceResponse<RestAgentCronJob>>(
      `/agent-cron-jobs/${id}`,
      { body: toRestBody(data) },
    );
    return toCronJobResponse(response);
  }

  async delete(id: string): Promise<{ message?: string; success: boolean }> {
    return restClient.delete(`/agent-cron-jobs/${id}`);
  }

  async resetExecutions(
    id: string,
    newMaxExecutions?: number,
  ): Promise<ServiceResponse<AgentCronJob>> {
    const response = await restClient.post<RestServiceResponse<RestAgentCronJob>>(
      '/agent-cron-jobs/reset-executions',
      {
        body: { id, new_max_executions: newMaxExecutions },
      },
    );
    return toCronJobResponse(response);
  }

  async getStats(): Promise<ServiceResponse<CronJobStats>> {
    const response =
      await restClient.get<RestServiceResponse<RestCronJobStats>>('/agent-cron-jobs/stats');

    return {
      ...response,
      data: {
        activeJobs: response.data.enabledCount ?? 0,
        completedExecutions: response.data.totalRuns ?? 0,
        pendingExecutions: 0,
        totalJobs: response.data.totalJobs ?? 0,
      },
    };
  }

  async getNearDepletion(threshold: number = 5) {
    const response = await restClient.get<RestServiceResponse<RestAgentCronJob[]>>(
      '/agent-cron-jobs/near-depletion',
      {
        params: { threshold } as any,
      },
    );
    return toCronJobListResponse(response);
  }

  async batchUpdateStatus(ids: string[], enabled: boolean) {
    return restClient.post('/agent-cron-jobs/batch-update-status', {
      body: { enabled, ids },
    });
  }
}

export const agentCronJobService = new AgentCronJobService();
