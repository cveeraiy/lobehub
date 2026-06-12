import { restClient } from '@/libs/rest';

interface GenerationWorkerResult {
  failures?: Array<{ generationId: string; message: string }>;
  processed: number;
  results?: GenerationWorkerResult[];
  status?: string;
}

class GenerationWorkerService {
  runPending = async (limit?: number) => {
    return restClient.post<GenerationWorkerResult>('/generation-workers/run-pending', {
      params: { limit },
    });
  };

  runTask = async (taskId: string) => {
    return restClient.post<GenerationWorkerResult>(
      `/generation-workers/tasks/${encodeURIComponent(taskId)}/run`,
    );
  };
}

export const generationWorkerService = new GenerationWorkerService();
