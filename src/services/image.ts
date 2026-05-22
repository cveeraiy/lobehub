import debug from 'debug';

import { restClient } from '@/libs/rest';
import type { CreateImageServicePayload } from '@/server/routers/lambda/image';

// Create debug logger
const log = debug('ethos-image:service');

export class AiImageService {
  async createImage(payload: CreateImageServicePayload) {
    log('Creating image with payload: %O', payload);

    try {
      const result = await restClient.post<{
        data: { batch: any; generations: any[] };
        success: boolean;
      }>('/image/create', {
        body: {
          generationTopicId: payload.generationTopicId,
          imageNum: payload.imageNum,
          model: payload.model,
          params: payload.params,
          provider: payload.provider,
        },
      });
      log('Image creation service call completed successfully: %O', {
        batchId: result.data?.batch?.id,
        generationCount: result.data?.generations?.length,
        success: result.success,
      });

      return result;
    } catch (error) {
      log('Image creation service call failed: %O', {
        error: (error as Error).message,
        payload,
      });

      throw error;
    }
  }
}

export const imageService = new AiImageService();
