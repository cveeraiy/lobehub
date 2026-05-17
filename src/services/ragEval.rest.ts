import {
  type CreateNewEvalDatasets,
  type CreateNewEvalEvaluation,
  type EvalDatasetRecord,
  type insertEvalDatasetsSchema,
  type RAGEvalDataSetItem,
  type RAGEvalEvaluationItem,
} from '@lobechat/types';

import { restClient } from '@/libs/rest';
import { uploadService } from '@/services/upload';

class RAGEvalService {
  // Dataset
  createDataset = async (params: CreateNewEvalDatasets): Promise<string | undefined> => {
    const result = await restClient.post<{ id: string }>('/rag-eval/datasets', { body: params });
    return result?.id;
  };

  getDatasets = async (knowledgeBaseId: string): Promise<RAGEvalDataSetItem[]> => {
    return restClient.get('/rag-eval/datasets', { params: { knowledgeBaseId } });
  };

  removeDataset = async (id: string): Promise<void> => {
    await restClient.delete(`/rag-eval/datasets/${id}`);
  };

  updateDataset = async (
    id: string,
    value: Partial<typeof insertEvalDatasetsSchema>,
  ): Promise<void> => {
    await restClient.put(`/rag-eval/datasets/${id}`, { body: value });
  };

  // Dataset Records
  getDatasetRecords = async (datasetId: string): Promise<EvalDatasetRecord[]> => {
    return restClient.get(`/rag-eval/datasets/${datasetId}/records`);
  };

  removeDatasetRecord = async (id: string): Promise<void> => {
    await restClient.delete(`/rag-eval/dataset-records/${id}`);
  };

  importDatasetRecords = async (datasetId: string, file: File): Promise<void> => {
    const { path } = await uploadService.uploadToServerS3(file, { directory: 'ragEval' });
    await restClient.post(`/rag-eval/datasets/${datasetId}/import`, { body: { pathname: path } });
  };

  // Evaluation
  createEvaluation = async (params: CreateNewEvalEvaluation): Promise<string | undefined> => {
    const result = await restClient.post<{ id: string }>('/rag-eval/evaluations', {
      body: params,
    });
    return result?.id;
  };

  getEvaluationList = async (knowledgeBaseId: string): Promise<RAGEvalEvaluationItem[]> => {
    return restClient.get('/rag-eval/evaluations', { params: { knowledgeBaseId } });
  };

  startEvaluationTask = async (id: string) => {
    return restClient.post(`/rag-eval/evaluations/${id}/start`);
  };

  removeEvaluation = async (id: string): Promise<void> => {
    await restClient.delete(`/rag-eval/evaluations/${id}`);
  };

  checkEvaluationStatus = async (id: string): Promise<{ success: boolean }> => {
    return restClient.get(`/rag-eval/evaluations/${id}/status`);
  };
}

export const ragEvalService = new RAGEvalService();
