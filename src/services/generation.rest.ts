import { restClient } from '@/libs/rest';

class GenerationService {
  async getGenerationStatus(generationId: string, asyncTaskId: string) {
    return restClient.get(`/generations/${generationId}/status`, {
      params: { asyncTaskId },
    });
  }

  async deleteGeneration(generationId: string) {
    return restClient.delete(`/generations/${generationId}`);
  }
}

export const generationService = new GenerationService();
