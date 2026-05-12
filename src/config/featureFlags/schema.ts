import { z } from 'zod';

// Define a union type for feature flag values: either boolean or array of user IDs
const FeatureFlagValue = z.union([z.boolean(), z.array(z.string())]);
const isDev = process.env.NODE_ENV === 'development';

export const FeatureFlagsSchema = z.object({
  check_updates: FeatureFlagValue.optional(),

  // settings
  provider_settings: FeatureFlagValue.optional(),

  openai_api_key: FeatureFlagValue.optional(),
  openai_proxy_url: FeatureFlagValue.optional(),

  // profile
  api_key_manage: FeatureFlagValue.optional(),
  edit_agent: FeatureFlagValue.optional(),

  ai_image: FeatureFlagValue.optional(),
  speech_to_text: FeatureFlagValue.optional(),
  token_counter: FeatureFlagValue.optional(),

  welcome_suggest: FeatureFlagValue.optional(),
  changelog: FeatureFlagValue.optional(),

  market: FeatureFlagValue.optional(),
  knowledge_base: FeatureFlagValue.optional(),

  rag_eval: FeatureFlagValue.optional(),

  // internal flag
  agent_self_iteration: FeatureFlagValue.optional(),
  agent_onboarding: FeatureFlagValue.optional(),
  agent_task: FeatureFlagValue.optional(),
  // Cloud feature flag. Keep here until cloud owns a separate runtime flag domain.
  auth_captcha: FeatureFlagValue.optional(),
  cloud_promotion: FeatureFlagValue.optional(),
  bot_channels: FeatureFlagValue.optional(),
  resources: FeatureFlagValue.optional(),
  starter_list: FeatureFlagValue.optional(),
  admin_panel: FeatureFlagValue.optional(),

  // Enterprise mode: when enabled, disables consumer features
  // (marketplace, image/video gen, public sharing, user-managed API keys, etc.)
  enterprise_mode: FeatureFlagValue.optional(),

  // the flags below can only be used with commercial license
  // if you want to use it in the commercial usage
  // please contact us for more information: hello@lobehub.com
  commercial_hide_github: FeatureFlagValue.optional(),
  commercial_hide_docs: FeatureFlagValue.optional(),
});

export type IFeatureFlags = z.infer<typeof FeatureFlagsSchema>;

/**
 * Evaluate a feature flag value against a user ID
 * @param flagValue - The feature flag value (boolean or array of user IDs)
 * @param userId - The current user ID
 * @returns boolean indicating if the feature is enabled for the user
 */
export const evaluateFeatureFlag = (
  flagValue: boolean | string[] | undefined,
  userId?: string,
): boolean | undefined => {
  if (typeof flagValue === 'boolean') return flagValue;

  if (Array.isArray(flagValue)) {
    return userId ? flagValue.includes(userId) : false;
  }
};

export const DEFAULT_FEATURE_FLAGS: IFeatureFlags = {
  provider_settings: true,

  openai_api_key: true,
  openai_proxy_url: true,

  api_key_manage: false,
  edit_agent: true,

  ai_image: false,

  check_updates: true,
  welcome_suggest: true,
  token_counter: true,

  knowledge_base: true,
  rag_eval: false,

  agent_self_iteration: isDev,
  agent_onboarding: isDev,
  agent_task: isDev,
  auth_captcha: true,
  cloud_promotion: false,

  market: false,
  speech_to_text: true,
  changelog: true,
  bot_channels: false,
  resources: false,
  starter_list: false,
  admin_panel: isDev,

  enterprise_mode: false,

  // the flags below can only be used with commercial license
  // if you want to use it in the commercial usage
  // please contact us for more information: hello@lobehub.com
  commercial_hide_github: false,
  commercial_hide_docs: false,
};

export const mapFeatureFlagsEnvToState = (config: IFeatureFlags, userId?: string) => {
  const isEnterprise = evaluateFeatureFlag(config.enterprise_mode, userId);

  return {
    isAgentEditable: evaluateFeatureFlag(config.edit_agent, userId),
    isEnterprise,
    showProvider: isEnterprise ? false : evaluateFeatureFlag(config.provider_settings, userId),

    showOpenAIApiKey: isEnterprise ? false : evaluateFeatureFlag(config.openai_api_key, userId),
    showOpenAIProxyUrl: isEnterprise ? false : evaluateFeatureFlag(config.openai_proxy_url, userId),

    showApiKeyManage: evaluateFeatureFlag(config.api_key_manage, userId),

    showAiImage: isEnterprise ? false : evaluateFeatureFlag(config.ai_image, userId),
    showChangelog: isEnterprise ? false : evaluateFeatureFlag(config.changelog, userId),

    enableCheckUpdates: isEnterprise ? false : evaluateFeatureFlag(config.check_updates, userId),
    showWelcomeSuggest: evaluateFeatureFlag(config.welcome_suggest, userId),

    enableKnowledgeBase: evaluateFeatureFlag(config.knowledge_base, userId),
    enableRAGEval: isEnterprise ? false : evaluateFeatureFlag(config.rag_eval, userId),
    enableAgentSelfIteration: evaluateFeatureFlag(config.agent_self_iteration, userId),
    enableAgentOnboarding: evaluateFeatureFlag(config.agent_onboarding, userId),
    enableAgentTask: evaluateFeatureFlag(config.agent_task, userId),
    enableAuthCaptcha: evaluateFeatureFlag(config.auth_captcha, userId),

    showCloudPromotion: isEnterprise ? false : evaluateFeatureFlag(config.cloud_promotion, userId),

    showMarket: isEnterprise ? false : evaluateFeatureFlag(config.market, userId),
    enableSTT: evaluateFeatureFlag(config.speech_to_text, userId),

    enableBotChannels: evaluateFeatureFlag(config.bot_channels, userId),
    enableResources: evaluateFeatureFlag(config.resources, userId),
    showStarterList: evaluateFeatureFlag(config.starter_list, userId),
    showAdminPanel: evaluateFeatureFlag(config.admin_panel, userId),

    hideGitHub: isEnterprise ? true : evaluateFeatureFlag(config.commercial_hide_github, userId),
    hideDocs: evaluateFeatureFlag(config.commercial_hide_docs, userId),
  };
};

export type IFeatureFlagsState = ReturnType<typeof mapFeatureFlagsEnvToState>;
