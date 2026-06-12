import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { generationService } from '../generation';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

describe('GenerationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getGenerationStatus should call REST with correct params', async () => {
    const generationId = 'test-generation-id';
    const asyncTaskId = 'test-async-task-id';

    await generationService.getGenerationStatus(generationId, asyncTaskId);

    expect(restClient.get).toBeCalledWith(`/generations/${generationId}/status`, {
      params: { asyncTaskId },
    });
  });

  it('deleteGeneration should call REST with correct params', async () => {
    const generationId = 'test-generation-id';

    await generationService.deleteGeneration(generationId);

    expect(restClient.delete).toBeCalledWith(`/generations/${generationId}`);
  });
});
