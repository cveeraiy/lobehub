import debug from 'debug';

import { restClient } from '@/libs/rest';
import type { CreateVideoServicePayload } from '@/server/routers/lambda/video';

const log = debug('ethos-video:service');

export class AiVideoService {
  async createVideo(payload: CreateVideoServicePayload) {
    log('Creating video with payload: %O', payload);

    try {
      const result = await restClient.post<{
        data: { batch: any; generations: any[] };
        success: boolean;
      }>('/video/create', {
        body: {
          generationTopicId: payload.generationTopicId,
          model: payload.model,
          params: payload.params,
          provider: payload.provider,
        },
      });
      log('Video creation service call completed: %O', {
        batchId: result.data?.batch?.id,
        generationCount: result.data?.generations?.length,
        success: result.success,
      });

      return result;
    } catch (error) {
      log('Video creation service call failed: %O', {
        error: (error as Error).message,
        payload,
      });

      throw error;
    }
  }
}

export const videoService = new AiVideoService();
