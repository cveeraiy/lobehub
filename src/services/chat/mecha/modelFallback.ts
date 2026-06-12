import { DEFAULT_AGENT_CONFIG } from '@/const/settings';
import { getAiInfraStoreState } from '@/store/aiInfra';

export const resolveEnabledChatModelConfig = (model?: string | null, provider?: string | null) => {
  const aiInfraState = getAiInfraStoreState();
  const enabledModels = aiInfraState.enabledAiModels || [];
  const enabledChatProviders = aiInfraState.enabledChatModelList || [];

  const currentModel = enabledModels.find(
    (item) => item.type === 'chat' && item.id === model && item.providerId === provider,
  );
  if (currentModel && provider) return { model: currentModel.id, provider };

  const isKnownAiProvider = aiInfraState.aiProviderList?.some((item) => item.id === provider);
  if (model && provider && provider !== 'lobehub' && !isKnownAiProvider) return { model, provider };

  const firstProvider = enabledChatProviders[0];
  const firstProviderModel = firstProvider?.children?.[0];
  if (firstProvider?.id && firstProviderModel?.id) {
    return { model: firstProviderModel.id, provider: firstProvider.id };
  }

  const firstEnabledModel = enabledModels.find((item) => item.type === 'chat' && item.providerId);
  if (firstEnabledModel?.providerId) {
    return { model: firstEnabledModel.id, provider: firstEnabledModel.providerId };
  }

  return {
    model: model || DEFAULT_AGENT_CONFIG.model,
    provider: provider || DEFAULT_AGENT_CONFIG.provider,
  };
};
