import { resolveEnabledChatModelConfig } from '@/services/chat/mecha/modelFallback';
import { useAgentStore } from '@/store/agent';
import { agentSelectors } from '@/store/agent/selectors';
import { useAiInfraStore } from '@/store/aiInfra';

export const useModelAndProvider = (modelProp?: string, providerProp?: string) => {
  const [storeModel, storeProvider] = useAgentStore((s) => [
    agentSelectors.currentAgentModel(s),
    agentSelectors.currentAgentModelProvider(s),
  ]);
  useAiInfraStore((s) => [s.enabledAiModels, s.enabledChatModelList]);

  const model = modelProp ?? storeModel;
  const provider = providerProp ?? storeProvider;

  return resolveEnabledChatModelConfig(model, provider);
};
