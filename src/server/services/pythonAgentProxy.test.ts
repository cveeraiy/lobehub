// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PythonAgentProxyService } from './pythonAgentProxy';

// Mock callPythonBackend — vi.hoisted ensures the mock fn is available at mock-hoist time
const mockCallPythonBackend = vi.hoisted(() => vi.fn());

vi.mock('@/server/utils/pythonBackend', () => ({
  callPythonBackend: mockCallPythonBackend,
  isPythonBackendEnabled: vi.fn(() => true),
}));

beforeEach(() => {
  mockCallPythonBackend.mockReset();
});

// ── Key conversion helpers (tested indirectly) ─────────────────────

describe('PythonAgentProxyService', () => {
  const userId = 'user-42';
  let service: PythonAgentProxyService;

  beforeEach(() => {
    service = new PythonAgentProxyService(userId);
  });

  describe('execAgent', () => {
    it('calls /api/ai-agent/exec with snake_case body and returns camelCase result', async () => {
      mockCallPythonBackend.mockResolvedValue({
        operation_id: 'op-123',
        auto_started: true,
        topic_id: 'topic-abc',
      });

      const result = await service.execAgent({
        agentId: 'agent-1',
        autoStart: true,
        prompt: 'hello',
        parentMessageId: 'msg-1',
      });

      // Verify call to Python backend
      expect(mockCallPythonBackend).toHaveBeenCalledOnce();
      const [path, uid, opts] = mockCallPythonBackend.mock.calls[0];
      expect(path).toBe('/api/ai-agent/exec');
      expect(uid).toBe(userId);

      // Verify body was converted to snake_case
      expect(opts.body).toEqual({
        agent_id: 'agent-1',
        auto_start: true,
        prompt: 'hello',
        parent_message_id: 'msg-1',
      });

      // Verify response was converted to camelCase
      expect(result).toEqual({
        operationId: 'op-123',
        autoStarted: true,
        topicId: 'topic-abc',
      });
    });

    it('handles undefined optional fields', async () => {
      mockCallPythonBackend.mockResolvedValue({ operation_id: 'op-1' });

      await service.execAgent({ prompt: 'test' });

      const body = mockCallPythonBackend.mock.calls[0][2].body;
      expect(body).toEqual({ prompt: 'test' });
    });
  });

  describe('execGroupAgent', () => {
    it('calls /api/ai-agent/exec-group with correct path', async () => {
      mockCallPythonBackend.mockResolvedValue({
        operation_id: 'op-456',
        topic_id: 'topic-xyz',
        is_create_new_topic: true,
      });

      const result = await service.execGroupAgent({
        agentId: 'agent-2',
        groupId: 'group-1',
        message: 'analyze this',
        topicId: null,
      });

      expect(mockCallPythonBackend.mock.calls[0][0]).toBe('/api/ai-agent/exec-group');
      expect(mockCallPythonBackend.mock.calls[0][2].body).toEqual({
        agent_id: 'agent-2',
        group_id: 'group-1',
        message: 'analyze this',
        topic_id: null,
      });
      expect(result).toEqual({
        operationId: 'op-456',
        topicId: 'topic-xyz',
        isCreateNewTopic: true,
      });
    });
  });

  describe('execSubAgentTask', () => {
    it('calls /api/ai-agent/exec-sub-agent with correct path', async () => {
      mockCallPythonBackend.mockResolvedValue({
        thread_id: 'thread-1',
        operation_id: 'op-789',
      });

      const result = await service.execSubAgentTask({
        agentId: 'agent-3',
        groupId: 'group-2',
        instruction: 'do the task',
        parentMessageId: 'msg-parent',
        topicId: 'topic-1',
        title: 'My Task',
        timeout: 60000,
      });

      expect(mockCallPythonBackend.mock.calls[0][0]).toBe('/api/ai-agent/exec-sub-agent');
      expect(mockCallPythonBackend.mock.calls[0][2].body).toEqual({
        agent_id: 'agent-3',
        group_id: 'group-2',
        instruction: 'do the task',
        parent_message_id: 'msg-parent',
        topic_id: 'topic-1',
        title: 'My Task',
        timeout: 60000,
      });
      expect(result).toEqual({
        threadId: 'thread-1',
        operationId: 'op-789',
      });
    });
  });

  describe('interruptTask', () => {
    it('calls /api/ai-agent/interrupt with correct path', async () => {
      mockCallPythonBackend.mockResolvedValue({ success: true });

      const result = await service.interruptTask({
        threadId: 'thread-99',
        operationId: 'op-99',
      });

      expect(mockCallPythonBackend.mock.calls[0][0]).toBe('/api/ai-agent/interrupt');
      expect(mockCallPythonBackend.mock.calls[0][2].body).toEqual({
        thread_id: 'thread-99',
        operation_id: 'op-99',
      });
      expect(result).toEqual({ success: true });
    });
  });

  // ── Key conversion edge cases ───────────────────────────────────

  describe('key conversion', () => {
    it('converts nested objects', async () => {
      mockCallPythonBackend.mockResolvedValue({
        nested_result: { inner_value: 42, deep_nested: { very_deep: true } },
      });

      const result = await service.execAgent({
        prompt: 'test',
        appContext: { sessionId: 'sess-1', userMeta: { displayName: 'Alice' } },
      });

      // Verify nested snake_case in request
      const body = mockCallPythonBackend.mock.calls[0][2].body;
      expect(body.app_context).toEqual({
        session_id: 'sess-1',
        user_meta: { display_name: 'Alice' },
      });

      // Verify nested camelCase in response
      expect(result).toEqual({
        nestedResult: { innerValue: 42, deepNested: { veryDeep: true } },
      });
    });

    it('converts arrays of objects', async () => {
      mockCallPythonBackend.mockResolvedValue({
        items: [{ item_name: 'a' }, { item_name: 'b' }],
      });

      const result = await service.execAgent({
        prompt: 'test',
        existingMessageIds: ['msg-1', 'msg-2'],
      });

      // Arrays of strings pass through unchanged
      const body = mockCallPythonBackend.mock.calls[0][2].body;
      expect(body.existing_message_ids).toEqual(['msg-1', 'msg-2']);

      // Arrays of objects get converted
      expect(result).toEqual({
        items: [{ itemName: 'a' }, { itemName: 'b' }],
      });
    });

    it('handles null and primitive values', async () => {
      mockCallPythonBackend.mockResolvedValue({
        count: 5,
        label: null,
        active: true,
      });

      const result = await service.execAgent({ prompt: 'test' });

      expect(result).toEqual({ count: 5, label: null, active: true });
    });
  });
});
