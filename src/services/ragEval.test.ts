import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ragEvalService } from './ragEval';

const mockRestPost = vi.hoisted(() => vi.fn());
const mockUploadToServerS3 = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    post: mockRestPost,
  },
}));

vi.mock('@/services/upload', () => ({
  uploadService: {
    uploadToServerS3: mockUploadToServerS3,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('RAGEvalService REST', () => {
  it('preserves raw string ids returned by Python create dataset', async () => {
    mockRestPost.mockResolvedValueOnce('dataset-1');

    const result = await ragEvalService.createDataset({
      knowledgeBaseId: 'kb-1',
      name: 'Dataset',
    });

    expect(result).toBe('dataset-1');
  });

  it('preserves object ids returned by compatible create endpoints', async () => {
    mockRestPost.mockResolvedValueOnce({ id: 'evaluation-1' });

    const result = await ragEvalService.createEvaluation({
      datasetId: 'dataset-1',
      knowledgeBaseId: 'kb-1',
      name: 'Evaluation',
    });

    expect(result).toBe('evaluation-1');
  });

  it('imports uploaded dataset records by pathname', async () => {
    const file = new File(['{"question":"Q1"}'], 'records.jsonl', {
      type: 'application/jsonl',
    });
    mockUploadToServerS3.mockResolvedValueOnce({ path: 'ragEval/1/records.jsonl' });
    mockRestPost.mockResolvedValueOnce({ imported: 1 });

    await ragEvalService.importDatasetRecords('dataset-1', file);

    expect(mockUploadToServerS3).toHaveBeenCalledWith(file, { directory: 'ragEval' });
    expect(mockRestPost).toHaveBeenCalledWith('/rag-eval/datasets/dataset-1/import', {
      body: { pathname: 'ragEval/1/records.jsonl' },
    });
  });
});
