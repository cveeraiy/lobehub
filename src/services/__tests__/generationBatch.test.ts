import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { generationBatchService } from '../generationBatch';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

describe('GenerationBatchService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getGenerationBatches should call REST with correct params', async () => {
    const topicId = 'test-topic-id';

    await generationBatchService.getGenerationBatches(topicId);

    expect(restClient.get).toBeCalledWith('/generation-batches', { params: { topicId } });
  });

  it('deleteGenerationBatch should call REST with correct params', async () => {
    const batchId = 'test-batch-id';

    await generationBatchService.deleteGenerationBatch(batchId);

    expect(restClient.delete).toBeCalledWith(`/generation-batches/${batchId}`);
  });
});
