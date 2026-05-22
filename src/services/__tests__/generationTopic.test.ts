import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import type { UpdateTopicValue } from '@/server/routers/lambda/generationTopic';

import { ServerService } from '../generationTopic';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('GenerationTopic ServerService', () => {
  let service: ServerService;

  beforeEach(() => {
    vi.clearAllMocks();
    service = new ServerService();
  });

  it('getAllGenerationTopics should call REST', async () => {
    await service.getAllGenerationTopics();
    expect(restClient.get).toBeCalledWith('/generation-topics', { params: undefined });
  });

  it('createTopic should call REST with undefined', async () => {
    await service.createTopic();
    expect(restClient.post).toBeCalledWith('/generation-topics', { body: undefined });
  });

  it('updateTopic should call REST with correct params', async () => {
    const id = 'test-topic-id';
    const data: UpdateTopicValue = {
      title: 'Updated Topic',
      coverUrl: 'https://example.com/cover.jpg',
    };

    await service.updateTopic(id, data);

    expect(restClient.put).toBeCalledWith(`/generation-topics/${id}`, { body: data });
  });

  it('updateTopicCover should call REST with correct params', async () => {
    const id = 'test-topic-id';
    const coverUrl = 'https://example.com/cover.jpg';

    await service.updateTopicCover(id, coverUrl);

    expect(restClient.put).toBeCalledWith(`/generation-topics/${id}/cover`, {
      body: { coverUrl },
    });
  });

  it('deleteTopic should call REST with correct params', async () => {
    const id = 'test-topic-id';

    await service.deleteTopic(id);

    expect(restClient.delete).toBeCalledWith(`/generation-topics/${id}`);
  });
});
