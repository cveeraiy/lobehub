import { restClient } from '@/libs/rest';
import type { Generation, GenerationBatch, GenerationBatchItem } from '@/types/generation';

type GenerationBatchWithAsyncTaskId = GenerationBatch & {
  generations: (Generation & { asyncTaskId?: string | null })[];
};

class GenerationBatchService {
  /**
   * Get generation batches for a specific topic
   */
  async getGenerationBatches(
    topicId: string,
    type?: 'image' | 'video',
  ): Promise<GenerationBatchWithAsyncTaskId[]> {
    return restClient.get('/generation-batches', {
      params: { topicId, type },
    });
  }

  /**
   * Delete a generation batch
   */
  async deleteGenerationBatch(batchId: string): Promise<GenerationBatchItem | undefined> {
    return restClient.delete(`/generation-batches/${batchId}`);
  }
}

export const generationBatchService = new GenerationBatchService();
