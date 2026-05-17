import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usageService } from './usage.rest';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('UsageService REST', () => {
  it('normalizes grouped usage logs and coerces object records to arrays', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        date: 1_767_225_600_000,
        day: '2026-01-01',
        records: {
          'record-1': {
            created_at: '2026-01-01T12:00:00.000Z',
            id: 'record-1',
            model: 'gpt-4o',
            provider: 'openai',
            spend: 0.01,
            total_input_tokens: 10,
            total_output_tokens: 20,
            total_tokens: 30,
            updated_at: '2026-01-01T12:00:01.000Z',
            user_id: 'user-1',
          },
        },
        total_requests: 1,
        total_spend: 0.01,
        total_tokens: 30,
      },
      {
        day: '2026-01-02',
        records: null,
      },
    ]);

    const result = await usageService.findAndGroupByDay('2026-01');

    expect(mockRestGet).toHaveBeenCalledWith('/usage/by-day', { params: { month: '2026-01' } });
    expect(result[0]).toMatchObject({
      day: '2026-01-01',
      totalRequests: 1,
      totalSpend: 0.01,
      totalTokens: 30,
    });
    expect(result[0].records).toHaveLength(1);
    expect(result[0].records[0]).toMatchObject({
      id: 'record-1',
      model: 'gpt-4o',
      provider: 'openai',
      totalInputTokens: 10,
      totalOutputTokens: 20,
      totalTokens: 30,
      userId: 'user-1',
    });
    expect(result[0].records[0].createdAt).toBeInstanceOf(Date);
    expect(result[1].records).toEqual([]);
  });

  it('normalizes monthly usage records from snake_case fields', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        created_at: '2026-01-01T12:00:00.000Z',
        id: 'record-1',
        model: 'gpt-4o',
        provider: 'openai',
        spend: 0.01,
        total_input_tokens: 10,
        total_output_tokens: 20,
        total_tokens: 30,
        updated_at: '2026-01-01T12:00:01.000Z',
        user_id: 'user-1',
      },
    ]);

    const result = await usageService.findByMonth('2026-01');

    expect(mockRestGet).toHaveBeenCalledWith('/usage/by-month', { params: { month: '2026-01' } });
    expect(result[0]).toMatchObject({
      id: 'record-1',
      totalInputTokens: 10,
      totalOutputTokens: 20,
      totalTokens: 30,
    });
    expect(result[0].updatedAt).toBeInstanceOf(Date);
  });
});
