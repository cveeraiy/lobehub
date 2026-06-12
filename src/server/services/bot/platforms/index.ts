// --------------- Core types & utilities ---------------
// --------------- Registry singleton ---------------
import { discord } from './discord/definition';
import { PlatformRegistry } from './registry';
import { slack } from './slack/definition';
import { telegram } from './telegram/definition';

export {
  allowFromField,
  type BotReplyLocale,
  displayToolCallsField,
  type DmDecision,
  type DmPolicy,
  type DmSettings,
  extractDmSettings,
  extractGroupSettings,
  extractUserAllowlist,
  getBotReplyLocale,
  getStepReactionEmoji,
  type GroupPolicy,
  type GroupSettings,
  makeDmPolicyField,
  makeGroupPolicyFields,
  makeServerIdField,
  makeUserIdField,
  normalizeAllowFromEntries,
  normalizeBotReplyLocale,
  RECEIVED_REACTION_EMOJI,
  shouldAllowSender,
  shouldHandleDm,
  shouldHandleGroup,
  THINKING_REACTION_EMOJI,
  type UserAllowlist,
  validateAccessSettings,
  WORKING_REACTION_EMOJI,
} from './const';
export { PlatformRegistry } from './registry';
export type {
  BotPlatformRedisClient,
  BotPlatformRuntimeContext,
  BotProviderConfig,
  ConnectionMode,
  ExtractFilesResult,
  FieldSchema,
  PlatformClient,
  PlatformDefinition,
  PlatformDocumentation,
  PlatformMessenger,
  SerializedPlatformDefinition,
  UsageStats,
  ValidationResult,
} from './types';
export { ClientFactory } from './types';
export type { ProviderConfigInput, ResolvedBotProviderConfig } from './utils';
export {
  buildRuntimeKey,
  extractDefaults,
  formatDuration,
  formatTokens,
  formatUsageStats,
  getEffectiveConnectionMode,
  mergeWithDefaults,
  parseRuntimeKey,
  resolveBotProviderConfig,
  resolveConnectionMode,
} from './utils';

// --------------- Platform definitions ---------------
export { discord } from './discord/definition';
export { slack } from './slack/definition';
export { telegram } from './telegram/definition';

export const platformRegistry = new PlatformRegistry();

platformRegistry.register(discord);
platformRegistry.register(telegram);
platformRegistry.register(slack);
