import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';
import { taskService } from '@/services/task';

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(restClient.delete).mockResolvedValue({ success: true });
  vi.mocked(restClient.get).mockResolvedValue({ data: null, success: true });
  vi.mocked(restClient.post).mockResolvedValue({ data: null, success: true });
  vi.mocked(restClient.put).mockResolvedValue({ data: null, success: true });
});

describe('TaskService', () => {
  describe('queries', () => {
    it('finds a task by id', async () => {
      await taskService.find('T-1');
      expect(restClient.get).toHaveBeenCalledWith('/tasks/T-1');
    });

    it('gets task detail by id', async () => {
      await taskService.getDetail('T-1');
      expect(restClient.get).toHaveBeenCalledWith('/tasks/T-1/detail');
    });

    it('lists tasks with REST-compatible filters', async () => {
      await taskService.list({
        assigneeAgentId: 'agt_1',
        limit: 50,
        offset: 0,
        parentTaskId: null,
        statuses: ['running'],
      });

      expect(restClient.get).toHaveBeenCalledWith('/tasks', {
        params: {
          assigneeAgentId: 'agt_1',
          limit: 50,
          offset: 0,
          parentIdentifier: undefined,
          parentTaskId: undefined,
          priorities: undefined,
          statuses: 'running,in_progress',
        },
      });
    });

    it('gets subtasks and task trees', async () => {
      await taskService.getSubtasks('T-1');
      await taskService.getTaskTree('T-1');

      expect(restClient.get).toHaveBeenCalledWith('/tasks/T-1/subtasks');
      expect(restClient.get).toHaveBeenCalledWith('/tasks/T-1/tree');
    });
  });

  describe('mutations', () => {
    it('creates tasks', async () => {
      const params = { instruction: 'Do something', name: 'Test' };
      await taskService.create(params);
      expect(restClient.post).toHaveBeenCalledWith('/tasks', { body: params });
    });

    it('updates tasks', async () => {
      await taskService.update('T-1', { name: 'Updated', priority: 1 });
      expect(restClient.put).toHaveBeenCalledWith('/tasks/T-1', {
        body: { name: 'Updated', priority: 1 },
      });
    });

    it('deletes tasks', async () => {
      await taskService.delete('T-1');
      expect(restClient.delete).toHaveBeenCalledWith('/tasks/T-1');
    });

    it('updates task status', async () => {
      await taskService.updateStatus('T-1', 'running');
      expect(restClient.put).toHaveBeenCalledWith('/tasks/T-1/status', {
        body: {
          error: undefined,
          status: 'running',
        },
      });
    });

    it('runs tasks with optional params', async () => {
      await taskService.run('T-1', { prompt: 'Focus on tests' });
      expect(restClient.post).toHaveBeenCalledWith('/tasks/T-1/run', {
        body: { prompt: 'Focus on tests' },
      });
    });

    it('adds comments', async () => {
      await taskService.addComment('T-1', 'Great work', { topicId: 'tpc_1' });
      expect(restClient.post).toHaveBeenCalledWith('/tasks/T-1/comments', {
        body: {
          content: 'Great work',
          topicId: 'tpc_1',
        },
      });
    });

    it('adds dependencies with the default relationship type', async () => {
      await taskService.addDependency('T-1', 'T-2');
      expect(restClient.post).toHaveBeenCalledWith('/tasks/T-1/dependencies', {
        body: {
          dependsOnId: 'T-2',
          type: 'blocks',
        },
      });
    });

    it('updates task config', async () => {
      await taskService.updateConfig('T-1', { model: 'gpt-4o', provider: 'openai' });
      expect(restClient.put).toHaveBeenCalledWith('/tasks/T-1/config', {
        body: { config: { model: 'gpt-4o', provider: 'openai' } },
      });
    });

    it('cancels task topics', async () => {
      await taskService.cancelTopic('tpc_1');
      expect(restClient.post).toHaveBeenCalledWith('/tasks/topics/tpc_1/cancel');
    });

    it('pins documents', async () => {
      await taskService.pinDocument('T-1', 'doc_1', 'user');
      expect(restClient.post).toHaveBeenCalledWith('/tasks/T-1/pinned-documents', {
        body: {
          documentId: 'doc_1',
          pinnedBy: 'user',
        },
      });
    });
  });

  describe('brief operations', () => {
    it('resolves briefs through REST', async () => {
      await taskService.resolveBrief('brief_1', { action: 'approve' });
      expect(restClient.post).toHaveBeenCalledWith('/briefs/brief_1/resolve', {
        body: {
          action: 'approve',
        },
      });
    });

    it('marks briefs read through REST', async () => {
      await taskService.markBriefRead('brief_1');
      expect(restClient.put).toHaveBeenCalledWith('/briefs/brief_1/read');
    });
  });
});
