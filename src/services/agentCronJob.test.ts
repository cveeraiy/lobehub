import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { agentCronJobService } from './agentCronJob';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AgentCronJobService REST', () => {
  it('maps create payloads to Python REST shape and restores frontend response shape', async () => {
    vi.mocked(restClient.post).mockResolvedValueOnce({
      data: {
        agent_id: 'agent-1',
        config: { content: 'run report', maxExecutions: 3, remainingExecutions: 3 },
        created_at: '2026-01-01T00:00:00.000Z',
        enabled: true,
        id: 'cron-1',
        schedule: '0 9 * * *',
        timezone: 'UTC',
        total_runs: 0,
        updated_at: '2026-01-01T00:00:00.000Z',
        user_id: 'user-1',
      },
      success: true,
    });

    const result = await agentCronJobService.create({
      agentId: 'agent-1',
      content: 'run report',
      cronPattern: '0 9 * * *',
      enabled: true,
      maxExecutions: 3,
      timezone: 'UTC',
    });

    expect(restClient.post).toHaveBeenCalledWith('/agent-cron-jobs', {
      body: {
        agent_id: 'agent-1',
        config: {
          content: 'run report',
          maxExecutions: 3,
        },
        enabled: true,
        schedule: '0 9 * * *',
        timezone: 'UTC',
      },
    });
    expect(result.data).toMatchObject({
      agentId: 'agent-1',
      content: 'run report',
      cronPattern: '0 9 * * *',
      id: 'cron-1',
      maxExecutions: 3,
      remainingExecutions: 3,
      totalExecutions: 0,
    });
  });

  it('does not send an empty config object for partial updates', async () => {
    vi.mocked(restClient.put).mockResolvedValueOnce({
      data: {
        agent_id: 'agent-1',
        config: { content: 'run report' },
        enabled: false,
        id: 'cron-1',
        schedule: '0 9 * * *',
      },
      success: true,
    });

    await agentCronJobService.update('cron-1', { enabled: false });

    expect(restClient.put).toHaveBeenCalledWith('/agent-cron-jobs/cron-1', {
      body: { enabled: false },
    });
  });

  it('maps stats from Python REST shape to frontend shape', async () => {
    vi.mocked(restClient.get).mockResolvedValueOnce({
      data: {
        enabledCount: 2,
        totalJobs: 4,
        totalRuns: 9,
      },
      success: true,
    });

    const result = await agentCronJobService.getStats();

    expect(restClient.get).toHaveBeenCalledWith('/agent-cron-jobs/stats');
    expect(result.data).toEqual({
      activeJobs: 2,
      completedExecutions: 9,
      pendingExecutions: 0,
      totalJobs: 4,
    });
  });
});
