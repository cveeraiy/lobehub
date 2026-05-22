import { type UIChatMessage } from '@lobechat/types';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { agentRuntimeService } from '../index';

const { contextEngineeringMock, createAgentToolsEngineMock, getAgentStoreStateMock } = vi.hoisted(
  () => ({
    contextEngineeringMock: vi.fn(),
    createAgentToolsEngineMock: vi.fn(),
    getAgentStoreStateMock: vi.fn(),
  }),
);

vi.mock('@/helpers/toolEngineering', () => ({
  createAgentToolsEngine: createAgentToolsEngineMock,
}));

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/services/chat/mecha', () => ({
  contextEngineering: contextEngineeringMock,
}));

vi.mock('@/store/agent', () => ({
  getAgentStoreState: getAgentStoreStateMock,
}));

vi.mock('@/store/agent/selectors', () => ({
  agentChatConfigSelectors: {
    currentChatConfig: vi.fn(() => ({ inputTemplate: 'input-template' })),
    enableHistoryCount: vi.fn(() => true),
    historyCount: vi.fn(() => 3),
    isAgentEnableSearch: vi.fn(() => false),
  },
  agentSelectors: {
    currentAgentConfig: vi.fn(() => ({
      model: 'gpt-4o',
      plugins: ['plugin-1'],
      provider: 'openai',
      systemRole: 'system-role',
    })),
    getAgentDocumentsById: vi.fn(() => () => undefined),
  },
}));

describe('AgentRuntimeService', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    createAgentToolsEngineMock.mockReturnValue({
      generateToolsDetailed: vi.fn(() => ({
        enabledToolIds: ['plugin-1'],
        tools: [{ function: { name: 'plugin-1____api-1' }, type: 'function' }],
      })),
      getEnabledPluginManifests: vi.fn(() => new Map([['plugin-1', { identifier: 'plugin-1' }]])),
    });

    contextEngineeringMock.mockResolvedValue([{ content: 'compiled', role: 'system' }]);
    vi.mocked(restClient.post).mockResolvedValue({ operationId: 'op-1' });
  });

  it('should keep agent documents optional when hydration returns undefined', async () => {
    const ensureAgentDocuments = vi.fn().mockResolvedValue(undefined);

    getAgentStoreStateMock.mockReturnValue({
      activeAgentId: 'agent-1',
      ensureAgentDocuments,
    });

    const messages = [{ content: 'Hello', role: 'user' }] as UIChatMessage[];

    await agentRuntimeService.createOperation({
      messages,
      userMessageId: 'msg-1',
    });

    expect(ensureAgentDocuments).toHaveBeenCalledWith('agent-1');
    expect(contextEngineeringMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentDocuments: undefined,
      }),
    );
    expect(restClient.post).toHaveBeenCalledWith('/ai-agent/create-operation', {
      body: expect.objectContaining({
        agent_config: expect.objectContaining({
          enableSearch: false,
          maxSteps: 50,
        }),
        messages: [{ content: 'compiled', role: 'system' }],
        model_runtime_config: {
          model: 'gpt-4o',
          provider: 'openai',
        },
        tool_manifest_map: {
          'plugin-1': { identifier: 'plugin-1' },
        },
        user_message_id: 'msg-1',
      }),
    });
  });

  it('should use current agent plugins when creating operation tools', async () => {
    getAgentStoreStateMock.mockReturnValue({
      activeAgentId: 'agent-1',
    });

    await agentRuntimeService.createOperation({
      messages: [{ id: 'msg-1', content: 'Hello', role: 'user' }] as UIChatMessage[],
      userMessageId: 'msg-1',
    });

    expect(createAgentToolsEngineMock).toHaveBeenCalledWith({
      model: 'gpt-4o',
      provider: 'openai',
    });
    expect(contextEngineeringMock).toHaveBeenCalledWith(
      expect.objectContaining({
        plugins: ['plugin-1'],
      }),
    );
  });
});
