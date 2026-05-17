import { type GenerationBatchItem } from '@/database/schemas';
import { restClient } from '@/libs/rest';
import { type Generation, type GenerationBatch } from '@/types/generation';

type GenerationBatchWithAsyncTaskId = GenerationBatch & {
  generations: (Generation & { asyncTaskId?: string | null })[];
};

class GenerationBatchService {
  async getGenerationBatches(
    topicId: string,
    type?: 'image' | 'video',
  ): Promise<GenerationBatchWithAsyncTaskId[]> {
    return restClient.get('/generation-batches', {
      params: { topicId, type } as any,
    });
  }

  async deleteGenerationBatch(batchId: string): Promise<GenerationBatchItem | undefined> {
    return restClient.delete(`/generation-batches/${batchId}`);
  }
}

export const generationBatchService = new GenerationBatchService();
