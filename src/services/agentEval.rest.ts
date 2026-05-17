import type { EvalRunInputConfig, RubricType } from '@lobechat/types';

import { restClient } from '@/libs/rest';

class AgentEvalService {
  // ============ Benchmark ============
  async listBenchmarks() {
    return restClient.get('/agent-eval/benchmarks');
  }

  async getBenchmark(id: string) {
    return restClient.get(`/agent-eval/benchmarks/${id}`);
  }

  async createBenchmark(params: {
    description?: string;
    identifier: string;
    metadata?: Record<string, unknown>;
    name: string;
    rubrics?: any[];
    tags?: string[];
  }) {
    return restClient.post('/agent-eval/benchmarks', { body: params });
  }

  async updateBenchmark(params: {
    description?: string;
    id: string;
    identifier: string;
    metadata?: Record<string, unknown>;
    name: string;
    tags?: string[];
  }) {
    const { id, ...body } = params;
    return restClient.put(`/agent-eval/benchmarks/${id}`, { body });
  }

  async deleteBenchmark(id: string) {
    return restClient.delete(`/agent-eval/benchmarks/${id}`);
  }

  // ============ Dataset ============
  async listDatasets(benchmarkId: string) {
    return restClient.get('/agent-eval/datasets', { params: { benchmarkId } });
  }

  async getDataset(id: string) {
    return restClient.get(`/agent-eval/datasets/${id}`);
  }

  async createDataset(params: {
    benchmarkId: string;
    description?: string;
    evalConfig?: { judgePrompt?: string };
    evalMode?: RubricType;
    identifier: string;
    metadata?: Record<string, unknown>;
    name: string;
  }) {
    return restClient.post('/agent-eval/datasets', { body: params });
  }

  async updateDataset(params: {
    description?: string;
    evalConfig?: { judgePrompt?: string } | null;
    evalMode?: RubricType | null;
    id: string;
    metadata?: Record<string, unknown>;
    name: string;
  }) {
    const { id, ...body } = params;
    return restClient.put(`/agent-eval/datasets/${id}`, { body });
  }

  async deleteDataset(id: string) {
    return restClient.delete(`/agent-eval/datasets/${id}`);
  }

  async parseDatasetFile(params: { filename?: string; pathname: string }) {
    return restClient.post('/agent-eval/datasets/parse-file', { body: params });
  }

  async importDataset(params: {
    datasetId: string;
    pathname: string;
    filename?: string;
    format?: 'json' | 'jsonl' | 'csv' | 'xlsx';
    fieldMapping: {
      input: string;
      expected?: string;
      expectedDelimiter?: string;
      category?: string;
      choices?: string;
      metadata?: Record<string, string>;
      sortOrder?: string;
    };
  }) {
    return restClient.post('/agent-eval/datasets/import', { body: params });
  }

  // ============ Test Case ============
  async listTestCases(params: { datasetId: string; limit?: number; offset?: number }) {
    return restClient.get('/agent-eval/test-cases', { params: params as any });
  }

  async createTestCase(params: {
    content: {
      category?: string;
      choices?: string[];
      expected?: string;
      input: string;
    };
    datasetId: string;
    evalConfig?: { judgePrompt?: string };
    evalMode?: RubricType;
    metadata?: {
      difficulty?: 'easy' | 'medium' | 'hard';
      tags?: string[];
    };
  }) {
    return restClient.post('/agent-eval/test-cases', { body: params });
  }

  async updateTestCase(params: {
    id: string;
    content?: {
      category?: string;
      expected?: string;
      input: string;
    };
    evalConfig?: { judgePrompt?: string } | null;
    evalMode?: RubricType | null;
    metadata?: Record<string, unknown>;
    sortOrder?: number;
  }) {
    const { id, ...body } = params;
    return restClient.put(`/agent-eval/test-cases/${id}`, { body });
  }

  async deleteTestCase(id: string) {
    return restClient.delete(`/agent-eval/test-cases/${id}`);
  }

  // ============ Run ============
  async listRuns(params: { benchmarkId?: string; datasetId?: string }) {
    return restClient.get('/agent-eval/runs', { params: params as any });
  }

  async getRunDetails(id: string) {
    return restClient.get(`/agent-eval/runs/${id}`);
  }

  async getRunResults(id: string) {
    return restClient.get(`/agent-eval/runs/${id}/results`);
  }

  async createRun(params: {
    config?: EvalRunInputConfig;
    datasetId: string;
    name?: string;
    targetAgentId?: string;
  }) {
    return restClient.post('/agent-eval/runs', { body: params });
  }

  async startRun(id: string, force?: boolean) {
    return restClient.post(`/agent-eval/runs/${id}/start`, { body: { force } });
  }

  async abortRun(id: string) {
    return restClient.post(`/agent-eval/runs/${id}/abort`);
  }

  async retryRunErrors(id: string) {
    return restClient.post(`/agent-eval/runs/${id}/retry-errors`);
  }

  async retryRunCase(runId: string, testCaseId: string) {
    return restClient.post(`/agent-eval/runs/${runId}/retry-case`, { body: { testCaseId } });
  }

  async resumeRunCase(runId: string, testCaseId: string, threadId?: string) {
    return restClient.post(`/agent-eval/runs/${runId}/resume-case`, {
      body: { testCaseId, threadId },
    });
  }

  async batchResumeRunCases(
    runId: string,
    targets: Array<{ testCaseId: string; threadId?: string }>,
  ) {
    return restClient.post(`/agent-eval/runs/${runId}/batch-resume`, { body: { targets } });
  }

  async getResumableCases(runId: string) {
    return restClient.get(`/agent-eval/runs/${runId}/resumable-cases`);
  }

  async updateRun(params: {
    config?: EvalRunInputConfig;
    datasetId?: string;
    id: string;
    name?: string;
    targetAgentId?: string | null;
  }) {
    const { id, ...body } = params;
    return restClient.put(`/agent-eval/runs/${id}`, { body });
  }

  async deleteRun(id: string) {
    return restClient.delete(`/agent-eval/runs/${id}`);
  }
}

export const agentEvalService = new AgentEvalService();
