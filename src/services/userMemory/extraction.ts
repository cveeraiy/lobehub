import {
  type AsyncTaskStatus,
  type IAsyncTaskError,
  type UserMemoryExtractionMetadata,
} from '@lobechat/types';

import { restClient } from '@/libs/rest';

export interface MemoryExtractionTask {
  error?: IAsyncTaskError | null;
  id: string;
  metadata: UserMemoryExtractionMetadata;
  status: AsyncTaskStatus;
}

export interface RequestMemoryExtractionParams {
  fromDate?: Date;
  toDate?: Date;
}

export interface RequestMemoryExtractionResult extends MemoryExtractionTask {
  deduped: boolean;
}

class MemoryExtractionService {
  requestFromChatTopics = async (
    params: RequestMemoryExtractionParams,
  ): Promise<RequestMemoryExtractionResult> => {
    return restClient.post('/user-memory/extraction/from-chat-topics', { body: params });
  };

  getTask = async (taskId?: string): Promise<MemoryExtractionTask | null> => {
    return restClient.get('/user-memory/extraction/task', {
      params: taskId ? { taskId } : undefined,
    });
  };
}

export const memoryExtractionService = new MemoryExtractionService();
