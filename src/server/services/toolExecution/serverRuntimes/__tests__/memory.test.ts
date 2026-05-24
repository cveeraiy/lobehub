import { describe, expect, it, vi } from 'vitest';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import { memoryRuntime } from '../memory';

vi.mock('@/server/utils/pythonBackend');

describe('memoryRuntime', () => {
  it('has correct identifier', () => {
    expect(memoryRuntime.identifier).toBe('lobe-user-memory');
  });

  it('calls Python tool execution with memory permission context', async () => {
    vi.mocked(callPythonBackend).mockResolvedValue({
      result: JSON.stringify({ content: 'ok', success: true }),
    });
    const runtime = memoryRuntime.factory({
      memoryToolPermission: 'read-only',
      toolManifestMap: {},
      userId: 'user-1',
    });

    const result = await runtime.addPreferenceMemory({
      summary: 'Likes terse answers',
      title: 'Style',
    });

    expect(result).toEqual({ content: 'ok', success: true });
    expect(callPythonBackend).toHaveBeenCalledWith('/api/tools/run', 'user-1', {
      body: {
        arguments: {
          summary: 'Likes terse answers',
          title: 'Style',
          toolPermission: 'read-only',
        },
        tool_name: 'lobe-user-memory__addPreferenceMemory',
      },
    });
  });

  it('throws at execution time if userId is missing', async () => {
    const runtime = memoryRuntime.factory({ toolManifestMap: {} });

    await expect(runtime.searchUserMemory({ queries: ['Ada'] })).rejects.toThrow(
      'userId is required for Memory execution',
    );
  });
});
