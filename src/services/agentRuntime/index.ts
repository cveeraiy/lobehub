import type { AgentContextDocument } from '@lobechat/context-engine';
import { type UIChatMessage } from '@lobechat/types';

import { createAgentToolsEngine } from '@/helpers/toolEngineering';
import { restClient } from '@/libs/rest';
import { type HumanInterventionRequest } from '@/services/agentRuntime/type';
import { contextEngineering } from '@/services/chat/mecha';
import { getAgentStoreState } from '@/store/agent';
import { agentChatConfigSelectors, agentSelectors } from '@/store/agent/selectors';

export { agentRuntimeClient } from './client';
export * from './type';

interface AgentOperationRequest {
  appSessionId?: string;
  autoStart?: boolean;
  messages: UIChatMessage[];
  threadId?: string;
  topicId?: string;
  userMessageId: string;
}

class AgentRuntimeService {
  createOperation = async (data: AgentOperationRequest) => {
    const agentStoreState = getAgentStoreState();
    const agentConfig = agentSelectors.currentAgentConfig(agentStoreState);
    const chatConfig = agentChatConfigSelectors.currentChatConfig(agentStoreState);
    let agentDocuments: AgentContextDocument[] | undefined = agentSelectors.getAgentDocumentsById(
      agentStoreState.activeAgentId || '',
    )(agentStoreState);

    if (agentStoreState.activeAgentId && agentDocuments === undefined) {
      try {
        agentDocuments = await agentStoreState.ensureAgentDocuments(agentStoreState.activeAgentId);
      } catch (error) {
        console.error('[AgentRuntimeService] Failed to ensure agent documents:', error);
      }
    }

    const modelRuntimeConfig = {
      model: agentConfig.model,
      provider: agentConfig.provider!,
    };

    const toolsEngine = createAgentToolsEngine(modelRuntimeConfig);

    const { tools, enabledToolIds } = toolsEngine.generateToolsDetailed({
      model: agentConfig.model,
      provider: agentConfig.provider!,
      toolIds: agentConfig.plugins,
    });

    const llmMessages = await contextEngineering({
      agentDocuments,
      agentId: agentStoreState.activeAgentId,
      enableHistoryCount: agentChatConfigSelectors.enableHistoryCount(agentStoreState),
      historyCount: agentChatConfigSelectors.historyCount(agentStoreState) + 1,
      inputTemplate: chatConfig.inputTemplate,
      messages: data.messages as any,
      ...modelRuntimeConfig,
      plugins: agentConfig.plugins,
      systemRole: agentConfig.systemRole,
      tools: enabledToolIds,
    });

    const toolManifestMap = Object.fromEntries(
      toolsEngine.getEnabledPluginManifests(enabledToolIds).entries(),
    );

    return await restClient.post('/ai-agent/create-operation', {
      body: {
        agent_config: {
          enableSearch: agentChatConfigSelectors.isAgentEnableSearch(agentStoreState),
          maxSteps: 50,
        },
        agent_id: agentStoreState.activeAgentId || undefined,
        app_session_id: data.appSessionId,
        auto_start: data.autoStart,
        messages: llmMessages,
        model_runtime_config: modelRuntimeConfig,
        thread_id: data.threadId,
        tool_manifest_map: toolManifestMap,
        tools,
        topic_id: data.topicId,
        user_message_id: data.userMessageId,
      },
    });
  };

  async getOperationStatus(operationId: string, includeHistory = false): Promise<any> {
    return await restClient.get('/ai-agent/operation-status', {
      params: { includeHistory, operationId },
    });
  }

  async handleHumanIntervention(request: HumanInterventionRequest): Promise<any> {
    return await restClient.post('/ai-agent/process-human-intervention', {
      body: {
        action: request.action,
        data: request.data,
        operation_id: request.operationId,
        reason: request.reason,
        step_index: 0,
      },
    });
  }
}

export const agentRuntimeService = new AgentRuntimeService();
