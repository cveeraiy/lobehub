import { describe, expect, it, vi } from 'vitest';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import { notebookRuntime } from '../notebook';

vi.mock('@/server/utils/pythonBackend');

describe('notebookRuntime', () => {
  it('should have correct identifier', () => {
    expect(notebookRuntime.identifier).toBe('lobe-notebook');
  });

  it('should create runtime from factory with valid context', () => {
    const context = {
      serverDB: {} as any,
      toolManifestMap: {},
      topicId: 'topic-1',
      userId: 'user-1',
    };

    const runtime = notebookRuntime.factory(context);

    expect(runtime).toBeDefined();
    expect(typeof runtime.createDocument).toBe('function');
    expect(typeof runtime.updateDocument).toBe('function');
    expect(typeof runtime.getDocument).toBe('function');
    expect(typeof runtime.deleteDocument).toBe('function');
  });

  it('should call Python tool execution with topic and task context', async () => {
    const context = {
      taskId: 'task-1',
      toolManifestMap: {},
      topicId: 'topic-1',
      userId: 'user-1',
    };
    vi.mocked(callPythonBackend).mockResolvedValue({
      result: JSON.stringify({ content: 'ok', success: true }),
    });

    const runtime = notebookRuntime.factory(context);
    const result = await runtime.createDocument({ content: 'body', title: 'Doc' });

    expect(result).toEqual({ content: 'ok', success: true });
    expect(callPythonBackend).toHaveBeenCalledWith('/api/tools/run', 'user-1', {
      body: {
        arguments: {
          content: 'body',
          taskId: 'task-1',
          title: 'Doc',
          topicId: 'topic-1',
        },
        tool_name: 'lobe-notebook__createDocument',
      },
    });
  });

  it('should throw at execution time if userId is missing', async () => {
    const context = {
      toolManifestMap: {},
    };
    const runtime = notebookRuntime.factory(context);

    await expect(runtime.getDocument({ id: 'doc-1' })).rejects.toThrow(
      'userId is required for Notebook execution',
    );
  });
});
