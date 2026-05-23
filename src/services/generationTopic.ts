import type { GenerationTopicItem } from '@/database/schemas';
import { restClient } from '@/libs/rest';
import type { ImageGenerationTopic } from '@/types/generation';
import type { UpdateGenerationTopicValue } from '@/types/mediaGeneration';

export class ServerService {
  async getAllGenerationTopics(type?: 'image' | 'video'): Promise<ImageGenerationTopic[]> {
    return restClient.get('/generation-topics', {
      params: type ? { type } : undefined,
    });
  }

  async createTopic(type?: 'image' | 'video'): Promise<string> {
    return restClient.post('/generation-topics', {
      body: type ? { type } : undefined,
    });
  }

  async updateTopic(
    id: string,
    data: UpdateGenerationTopicValue,
  ): Promise<GenerationTopicItem | undefined> {
    return restClient.put(`/generation-topics/${id}`, { body: data });
  }

  async updateTopicCover(id: string, coverUrl: string): Promise<GenerationTopicItem | undefined> {
    return restClient.put(`/generation-topics/${id}/cover`, { body: { coverUrl } });
  }

  async deleteTopic(id: string): Promise<GenerationTopicItem | undefined> {
    return restClient.delete(`/generation-topics/${id}`);
  }
}

export const generationTopicService = new ServerService();
